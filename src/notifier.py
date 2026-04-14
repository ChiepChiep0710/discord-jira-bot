from collections import defaultdict

import discord

from src import config
from src.jira_client import JiraIssue

PRIORITY_EMOJI = {
    "Highest": "🔴",
    "High":    "🟠",
    "Medium":  "🟡",
    "Low":     "🔵",
    "Lowest":  "⚪",
}

STATUS_EMOJI = {
    "To Do":       "⬜",
    "To do":       "⬜",
    "In Progress": "🔄",
    "In Review":   "👀",
    "Testing":     "🧪",
    "Blocked":     "🚫",
}


def _priority_emoji(priority: str) -> str:
    return PRIORITY_EMOJI.get(priority, "🟡")


def _status_emoji(status: str) -> str:
    return STATUS_EMOJI.get(status, "📌")


def _group_by_status(issues: list[JiraIssue]) -> dict[str, list[JiraIssue]]:
    groups: dict[str, list[JiraIssue]] = defaultdict(list)
    for issue in issues:
        groups[issue.status].append(issue)
    return groups


def _fmt_issues(issue_list: list[JiraIssue], show_assignee: bool = False) -> str:
    lines = []
    for issue in issue_list:
        p = _priority_emoji(issue.priority)
        line = f"{p} **[{issue.key}]({issue.url})** — {issue.summary}"
        if show_assignee:
            line += f"\n  👤 {issue.assignee_name}"
        lines.append(line)
    return "\n".join(lines)


def build_channel_embed(issues: list[JiraIssue]) -> discord.Embed:
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")
    embed = discord.Embed(
        title=f"📋 Active Sprint — {config.JIRA_PROJECT_KEY} — {today}",
        color=discord.Color.blue(),
    )

    if not issues:
        embed.description = "✅ Không có task nào trong active sprint!"
        embed.set_footer(text="Jira Reminder Bot")
        return embed

    # Tóm tắt theo assignee: tên + số issue theo từng status
    by_assignee: dict[str, list[JiraIssue]] = defaultdict(list)
    for issue in issues:
        by_assignee[issue.assignee_name].append(issue)

    lines = []
    for name, user_issues in sorted(by_assignee.items()):
        status_counts = defaultdict(int)
        for i in user_issues:
            status_counts[i.status] += 1
        status_str = " • ".join(
            f"{_status_emoji(s)}{s}: {c}" for s, c in status_counts.items()
        )
        lines.append(f"👤 **{name}** ({len(user_issues)}) — {status_str}")

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Jira Reminder Bot • Tổng: {len(issues)} task • Chi tiết xem DM")
    return embed


def build_dm_embed(issues: list[JiraIssue], assignee_name: str) -> discord.Embed:
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")
    embed = discord.Embed(
        title=f"👋 Task của bạn trong Sprint — {today}",
        description=f"Xin chào **{assignee_name}**, đây là các task đang assign cho bạn:",
        color=discord.Color.orange(),
    )

    for status, group in _group_by_status(issues).items():
        s_emoji = _status_emoji(status)
        embed.add_field(
            name=f"{s_emoji} {status} ({len(group)})",
            value=_fmt_issues(group, show_assignee=False),
            inline=False,
        )

    embed.set_footer(text="Jira Reminder Bot • Chúc bạn làm việc hiệu quả!")
    return embed


def build_detail_embeds(issues: list[JiraIssue], assignee_name: str) -> list[discord.Embed]:
    """Trả về list embed — mỗi embed một issue, hiển thị đầy đủ chi tiết."""
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")
    embeds = []

    # Embed tiêu đề tổng hợp
    header = discord.Embed(
        title=f"📋 Task của **{assignee_name}** — {today}",
        description=f"Tổng **{len(issues)}** task trong sprint hiện tại:",
        color=discord.Color.orange(),
    )
    for status, group in _group_by_status(issues).items():
        header.add_field(
            name=f"{_status_emoji(status)} {status}",
            value=str(len(group)),
            inline=True,
        )
    embeds.append(header)

    # Mỗi issue 1 embed
    for issue in issues:
        embed = discord.Embed(
            title=f"{_priority_emoji(issue.priority)} [{issue.key}] {issue.summary}",
            url=issue.url,
            color=discord.Color.og_blurple(),
        )
        embed.add_field(name="Trạng thái", value=f"{_status_emoji(issue.status)} {issue.status}", inline=True)
        embed.add_field(name="Độ ưu tiên", value=f"{_priority_emoji(issue.priority)} {issue.priority}", inline=True)
        if issue.epic_key:
            epic_url = f"{issue.url.split('/browse/')[0]}/browse/{issue.epic_key}"
            embed.add_field(name="Epic", value=f"[{issue.epic_name}]({epic_url})", inline=True)
        else:
            embed.add_field(name="Epic", value="—", inline=True)
        embeds.append(embed)

    return embeds


def build_remind_embeds(issues: list[JiraIssue]) -> list[discord.Embed]:
    """Gửi chi tiết task theo từng trạng thái, tách embed nếu quá dài."""
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")
    embeds = []

    # Embed header tổng hợp
    header = discord.Embed(
        title=f"📋 Active Sprint — {config.JIRA_PROJECT_KEY} — {today}",
        color=discord.Color.blue(),
    )
    if not issues:
        header.description = "✅ Không có task nào trong active sprint!"
        return [header]

    by_assignee: dict[str, list[JiraIssue]] = defaultdict(list)
    for issue in issues:
        by_assignee[issue.assignee_name].append(issue)
    summary_lines = []
    for name, user_issues in sorted(by_assignee.items()):
        status_counts: dict[str, int] = defaultdict(int)
        for i in user_issues:
            status_counts[i.status] += 1
        status_str = " • ".join(f"{_status_emoji(s)}{s}: {c}" for s, c in status_counts.items())
        summary_lines.append(f"👤 **{name}** ({len(user_issues)}) — {status_str}")
    header.description = "\n".join(summary_lines)
    header.set_footer(text=f"Tổng: {len(issues)} task")
    embeds.append(header)

    # Một embed per status, tự tách nếu quá 4000 ký tự
    MAX_DESC = 4000
    for status, group in _group_by_status(issues).items():
        s_emoji = _status_emoji(status)
        lines = []
        for issue in group:
            p = _priority_emoji(issue.priority)
            epic_str = f" • 🗂 {issue.epic_name}" if issue.epic_name else ""
            line = (
                f"{p} **[{issue.key}]({issue.url})** {issue.summary}\n"
                f"  👤 {issue.assignee_name} • {issue.priority}{epic_str}"
            )
            lines.append(line)

        # Tách thành nhiều embed nếu cần
        current_lines: list[str] = []
        current_len = 0
        part = 1
        total_parts = 1

        for line in lines:
            if current_len + len(line) + 1 > MAX_DESC:
                title = f"{s_emoji} {status} ({len(group)})" if total_parts == 1 else f"{s_emoji} {status} ({len(group)}) — phần {part}"
                e = discord.Embed(title=title, description="\n\n".join(current_lines), color=discord.Color.blue())
                embeds.append(e)
                current_lines = [line]
                current_len = len(line)
                part += 1
                total_parts += 1
            else:
                current_lines.append(line)
                current_len += len(line) + 1

        if current_lines:
            title = f"{s_emoji} {status} ({len(group)})" if total_parts == 1 else f"{s_emoji} {status} ({len(group)}) — phần {part}"
            e = discord.Embed(title=title, description="\n\n".join(current_lines), color=discord.Color.blue())
            embeds.append(e)

    return embeds


PRIORITY_ORDER = ["Highest", "High", "Medium", "Low", "Lowest"]


def build_priority_embeds(issues: list[JiraIssue]) -> list[discord.Embed]:
    """Báo cáo task nhóm theo priority, tách embed nếu quá dài."""
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")
    MAX_DESC = 4000
    embeds = []

    # Header tổng hợp
    header = discord.Embed(
        title=f"🎯 Báo cáo theo Priority — {config.JIRA_PROJECT_KEY} — {today}",
        color=discord.Color.purple(),
    )
    if not issues:
        header.description = "✅ Không có task nào trong active sprint!"
        return [header]

    by_priority: dict[str, list[JiraIssue]] = defaultdict(list)
    for issue in issues:
        by_priority[issue.priority].append(issue)

    summary_lines = []
    for p in PRIORITY_ORDER:
        if p in by_priority:
            summary_lines.append(f"{_priority_emoji(p)} **{p}**: {len(by_priority[p])} task")
    header.description = "\n".join(summary_lines)
    header.set_footer(text=f"Tổng: {len(issues)} task")
    embeds.append(header)

    # Một embed per priority theo thứ tự quan trọng
    for priority in PRIORITY_ORDER:
        group = by_priority.get(priority, [])
        if not group:
            continue

        lines = []
        for issue in group:
            s = _status_emoji(issue.status)
            epic_str = f" • 🗂 {issue.epic_name}" if issue.epic_name else ""
            line = (
                f"{_priority_emoji(priority)} **[{issue.key}]({issue.url})** {issue.summary}\n"
                f"  {s} {issue.status} • 👤 {issue.assignee_name}{epic_str}"
            )
            lines.append(line)

        current_lines: list[str] = []
        current_len = 0
        part = 1
        total_parts = 1

        for line in lines:
            if current_len + len(line) + 1 > MAX_DESC:
                title = f"{_priority_emoji(priority)} {priority} ({len(group)})" if total_parts == 1 else f"{_priority_emoji(priority)} {priority} ({len(group)}) — phần {part}"
                color = {
                    "Highest": discord.Color.red(),
                    "High": discord.Color.orange(),
                    "Medium": discord.Color.yellow(),
                    "Low": discord.Color.blue(),
                    "Lowest": discord.Color.greyple(),
                }.get(priority, discord.Color.blue())
                embeds.append(discord.Embed(title=title, description="\n\n".join(current_lines), color=color))
                current_lines = [line]
                current_len = len(line)
                part += 1
                total_parts += 1
            else:
                current_lines.append(line)
                current_len += len(line) + 1

        if current_lines:
            title = f"{_priority_emoji(priority)} {priority} ({len(group)})" if total_parts == 1 else f"{_priority_emoji(priority)} {priority} ({len(group)}) — phần {part}"
            color = {
                "Highest": discord.Color.red(),
                "High": discord.Color.orange(),
                "Medium": discord.Color.yellow(),
                "Low": discord.Color.blue(),
                "Lowest": discord.Color.greyple(),
            }.get(priority, discord.Color.blue())
            embeds.append(discord.Embed(title=title, description="\n\n".join(current_lines), color=color))

    return embeds


async def send_reminders(bot: discord.Client, issues: list[JiraIssue]) -> None:
    # 1. Gửi chi tiết theo trạng thái vào channel
    channel = bot.get_channel(config.DISCORD_CHANNEL_ID)
    if channel:
        for embed in build_remind_embeds(issues):
            await channel.send(embed=embed)

    # 2. DM từng assignee issue của họ
    by_assignee: dict[str, list[JiraIssue]] = defaultdict(list)
    for issue in issues:
        if issue.assignee_username:
            by_assignee[issue.assignee_username].append(issue)

    for jira_username, user_issues in by_assignee.items():
        discord_user_id = config.JIRA_DISCORD_USER_MAP.get(jira_username)
        if not discord_user_id:
            continue
        try:
            user = await bot.fetch_user(int(discord_user_id))
            await user.send(embed=build_dm_embed(user_issues, user_issues[0].assignee_name))
        except discord.Forbidden:
            print(f"[DM] Không thể nhắn cho user {discord_user_id} (đã tắt DM)")
        except discord.NotFound:
            print(f"[DM] Không tìm thấy Discord user {discord_user_id}")
