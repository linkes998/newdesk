"""
人工审核工作流 —— 状态机 + JSON 持久化。

每个审核条目状态流转：
    pending ──approve──→ approved ──publish──→ published
      │
      ├──reject──→ rejected
      │
      └──modify──→ pending (带修改记录)

核心设计：
- 审核条目以 ReviewItem 表示，包含事件、各平台文案、状态、修改历史
- ReviewQueue 管理所有条目，持久化到 data/review_queue.json
- 提供简单的 CLI 审核界面和 programmatic API
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 状态机
# ---------------------------------------------------------------------------

class ReviewStatus(str, Enum):
    PENDING = "pending"
    MODIFIED = "modified"       # 改过文案但还没批准
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


_VALID_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.PENDING: {ReviewStatus.MODIFIED, ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    ReviewStatus.MODIFIED: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    ReviewStatus.APPROVED: {ReviewStatus.PUBLISHED, ReviewStatus.PENDING, ReviewStatus.REJECTED},  # 允许反悔
    ReviewStatus.REJECTED: {ReviewStatus.PENDING},
    ReviewStatus.PUBLISHED: {},  # 终态
}


def can_transition(from_status: ReviewStatus, to_status: ReviewStatus) -> bool:
    return to_status in _VALID_TRANSITIONS.get(from_status, set())


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class ReviewItem:
    """单条审核条目。"""
    item_id: str                              # hash(title + url)
    event_title: str
    event_url: str
    event_summary: str
    event_score: float
    event_tags: list[str] = field(default_factory=list)

    # 各平台文案：{platform_key: text}
    drafts: dict[str, str] = field(default_factory=dict)

    # 当前状态
    status: str = ReviewStatus.PENDING.value

    # 修改历史：[{"timestamp": "...", "action": "modify|approve|reject|publish", "note": "...", "platform": "x"}]
    history: list[dict] = field(default_factory=list)

    # 发布结果（如果已发布）
    publish_results: dict[str, dict] = field(default_factory=dict)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def update(self, new_status: ReviewStatus, *, note: str = "", platform: str = "") -> None:
        if not can_transition(ReviewStatus(self.status), new_status):
            raise ValueError(
                f"状态不允许：{self.status} → {new_status.value} "
                f"（合法目标：{[s.value for s in _VALID_TRANSITIONS.get(ReviewStatus(self.status), set())]}）"
            )
        now = datetime.now(timezone.utc).isoformat()
        self.status = new_status.value
        self.updated_at = now
        self.history.append({
            "timestamp": now,
            "action": new_status.value,
            "note": note,
            "platform": platform,
        })

    def modify_draft(self, platform: str, new_text: str, *, note: str = "人工修改") -> None:
        """修改某个平台的文案，状态变为 modified。"""
        self.drafts[platform] = new_text
        now = datetime.now(timezone.utc).isoformat()
        self.status = ReviewStatus.MODIFIED.value if self.status == ReviewStatus.PENDING.value else self.status
        self.updated_at = now
        self.history.append({
            "timestamp": now,
            "action": "modify",
            "note": note,
            "platform": platform,
        })

    def approve(self, *, note: str = "") -> None:
        self.update(ReviewStatus.APPROVED, note=note or "审核通过")

    def reject(self, *, note: str = "") -> None:
        self.update(ReviewStatus.REJECTED, note=note or "审核拒绝")

    def mark_published(self, platform: str, result: dict) -> None:
        self.publish_results[platform] = result
        # 所有平台都成功标记为 published
        if result.get("success") and all(
            self.publish_results.get(p, {}).get("success") for p in self.drafts.keys() if p != platform
        ):
            self.update(ReviewStatus.PUBLISHED, platform=platform)

    def summary(self) -> str:
        lines = [
            f"[{self.status.upper()}] {self.event_title[:60]}",
            f"  分数: {self.event_score:.1f}  标签: {','.join(self.event_tags[:3])}",
            f"  链接: {self.event_url}",
        ]
        for platform, text in self.drafts.items():
            preview = text[:80].replace("\n", " ")
            lines.append(f"  [{platform}] {preview}...")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewItem":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# 队列管理
# ---------------------------------------------------------------------------

class ReviewQueue:
    """审核队列，持久化到单个 JSON 文件。"""

    def __init__(self, path: str | Path = "data/review_queue.json"):
        self.path = Path(path)
        self.items: list[ReviewItem] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self.items = [ReviewItem.from_dict(d) for d in raw.get("items", [])]
            except (json.JSONDecodeError, KeyError) as exc:
                print(f"⚠️  审核队列文件损坏 {exc}，重新初始化")
                self.items = []
        else:
            self.items = []
        self._loaded = True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "items": [item.to_dict() for item in self.items],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- 查询 ---

    def _ensure_loaded(self) -> None:
        self.load()

    def all(self) -> list[ReviewItem]:
        self._ensure_loaded()
        return self.items

    def by_status(self, status: ReviewStatus | str) -> list[ReviewItem]:
        self._ensure_loaded()
        if isinstance(status, ReviewStatus):
            status = status.value
        return [it for it in self.items if it.status == status]

    def pending(self) -> list[ReviewItem]:
        return self.by_status(ReviewStatus.PENDING)

    def find(self, item_id: str) -> Optional[ReviewItem]:
        self._ensure_loaded()
        for it in self.items:
            if it.item_id == item_id:
                return it
        return None

    def stats(self) -> dict[str, int]:
        self._ensure_loaded()
        counts: dict[str, int] = {s.value: 0 for s in ReviewStatus}
        for it in self.items:
            counts[it.status] = counts.get(it.status, 0) + 1
        return counts

    # --- 变更 ---

    def add(self, item: ReviewItem) -> None:
        self._ensure_loaded()
        # 去重：已存在则合并 drafts
        existing = self.find(item.item_id)
        if existing:
            for platform, text in item.drafts.items():
                if platform not in existing.drafts:
                    existing.drafts[platform] = text
            return
        self.items.append(item)
        self.save()

    def add_batch(self, items: list[ReviewItem]) -> None:
        for item in items:
            self.add(item)

    def approve(self, item_id: str, *, note: str = "") -> ReviewItem | None:
        item = self.find(item_id)
        if item is None:
            return None
        item.approve(note=note)
        self.save()
        return item

    def reject(self, item_id: str, *, note: str = "") -> ReviewItem | None:
        item = self.find(item_id)
        if item is None:
            return None
        item.reject(note=note)
        self.save()
        return item

    def modify_draft(self, item_id: str, platform: str, new_text: str) -> ReviewItem | None:
        item = self.find(item_id)
        if item is None:
            return None
        item.modify_draft(platform, new_text)
        self.save()
        return item

    def delete_published(self) -> int:
        """清理已发布的条目。返回删除数量。"""
        self._ensure_loaded()
        before = len(self.items)
        self.items = [it for it in self.items if it.status != ReviewStatus.PUBLISHED]
        deleted = before - len(self.items)
        if deleted:
            self.save()
        return deleted


# ---------------------------------------------------------------------------
# CLI 审核器（简化的命令行审核界面）
# ---------------------------------------------------------------------------

def run_interactive_review(queue: ReviewQueue | None = None) -> None:
    """启动交互式审核会话。"""
    queue = queue or ReviewQueue()
    queue.load()

    print("\n" + "=" * 50)
    print("📋 NewsDesk 人工审核中心 (输入 help 查看命令)")
    print("=" * 50)

    while True:
        stats = queue.stats()
        print(f"\n当前队列状态: pending={stats.get('pending', 0)}  "
              f"approved={stats.get('approved', 0)}  "
              f"rejected={stats.get('rejected', 0)}  "
              f"published={stats.get('published', 0)}")

        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 退出审核中心")
            break

        if cmd in ("quit", "exit", "q"):
            print("👋 退出")
            break

        elif cmd == "help":
            print("""
可用命令:
  list [status]        列出队列（可选状态过滤: pending/approved/rejected/published）
  show <id>            查看完整条目
  approve <id>         批准条目
  reject <id> [note]   拒绝条目（可加备注）
  modify <id> <plat>   编辑某平台文案（进入编辑器）
  stats                查看统计
  clean                清理已发布条目
  quit                 退出
            """.strip())

        elif cmd.startswith("list"):
            parts = cmd.split(maxsplit=1)
            filter_status = parts[1] if len(parts) > 1 else None
            items = queue.all()
            if filter_status:
                items = [it for it in items if it.status == filter_status]
            if not items:
                print("  队列为空")
                continue
            for it in items:
                print(f"  [{it.item_id[:8]}] {it.summary()}")

        elif cmd.startswith("show"):
            parts = cmd.split(maxsplit=1)
            if len(parts) < 2:
                print("  用法: show <item_id>")
                continue
            item = queue.find(parts[1])
            if not item:
                print(f"  找不到条目 {parts[1]}")
                continue
            print(f"\n{'='*50}")
            print(f"ID: {item.item_id}")
            print(f"标题: {item.event_title}")
            print(f"状态: {item.status}")
            print(f"标签: {', '.join(item.event_tags)}")
            print(f"链接: {item.event_url}")
            print(f"\n草稿:")
            for platform, text in item.drafts.items():
                print(f"\n  --- [{platform}] ---")
                print(f"  {text}")
            if item.history:
                print(f"\n历史 ({len(item.history)} 条):")
                for h in item.history[-5:]:
                    print(f"  {h['timestamp'][:16]} {h['action']} {h.get('note', '')}")

        elif cmd.startswith("approve"):
            parts = cmd.split(maxsplit=1)
            if len(parts) < 2:
                print("  用法: approve <item_id>")
                continue
            result = queue.approve(parts[1])
            if result:
                print(f"  ✅ 已批准 [{parts[1][:8]}]")
            else:
                print(f"  找不到条目 {parts[1]}")

        elif cmd.startswith("reject"):
            parts = cmd.split()
            if len(parts) < 2:
                print("  用法: reject <item_id> [note]")
                continue
            note = " ".join(parts[2:]) if len(parts) > 2 else ""
            result = queue.reject(parts[1], note=note)
            if result:
                print(f"  ❌ 已拒绝 [{parts[1][:8]}]")
            else:
                print(f"  找不到条目 {parts[1]}")

        elif cmd.startswith("modify"):
            parts = cmd.split()
            if len(parts) < 3:
                print("  用法: modify <item_id> <platform>")
                print("  platform: x / telegram / discord")
                continue
            item = queue.find(parts[1])
            if not item:
                print(f"  找不到条目 {parts[1]}")
                continue
            platform = parts[2]
            old_text = item.drafts.get(platform, "")
            print(f"\n  当前 [{platform}] 文案：\n  {'-'*40}")
            print(f"  {old_text}")
            print(f"  {'-'*40}")
            try:
                print("\n  输入新文案（Ctrl+D 或空行结束）：")
                lines: list[str] = []
                while True:
                    try:
                        line = input("  > ")
                    except EOFError:
                        break
                    if line == "" and lines:
                        break
                    lines.append(line)
                new_text = "\n".join(lines)
                if new_text.strip():
                    queue.modify_draft(parts[1], platform, new_text)
                    print(f"  ✏️  已修改 [{platform}]")
                else:
                    print("  未输入内容，取消")
            except KeyboardInterrupt:
                print("\n  取消编辑")

        elif cmd == "stats":
            for k, v in queue.stats().items():
                print(f"  {k}: {v}")

        elif cmd == "clean":
            deleted = queue.delete_published()
            print(f"  🗑️  已清理 {deleted} 条已发布记录")

        else:
            print(f"  未知命令 '{cmd}'，输入 help 查看帮助")
