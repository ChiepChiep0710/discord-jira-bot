import asyncio
import logging
import discord
from discord.ext import commands

from src import config
from src.scheduler import setup_scheduler, run_reminder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    logger.info(f"Bot đã đăng nhập: {bot.user} (id={bot.user.id})")
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info(
        f"Scheduler đã khởi động — nhắc lúc {config.REMIND_CRON_HOUR:02d}:{config.REMIND_CRON_MINUTE:02d} "
        f"(Thứ 2–6)"
    )


@bot.command(name="help", aliases=["guide", "huongdan"])
async def cmd_help(ctx: commands.Context):
    embed = discord.Embed(
        title="🤖 Jira Bot — Hướng dẫn sử dụng",
        description=f"Prefix: `!` — Project: **{config.JIRA_PROJECT_KEY}**",
        color=discord.Color.green(),
    )

    embed.add_field(
        name="📋 `!remind`",
        value="Gửi báo cáo toàn bộ task trong sprint hiện tại vào channel, nhóm theo **trạng thái**.",
        inline=False,
    )
    embed.add_field(
        name="🎯 `!priority` `[priority]`",
        value=(
            "Báo cáo task nhóm theo **độ ưu tiên**.\n"
            "Không truyền tham số → hiển thị tất cả.\n"
            "Ví dụ: `!priority High`, `!priority Highest`\n"
            "Giá trị hợp lệ: `Highest` `High` `Medium` `Low` `Lowest`"
        ),
        inline=False,
    )
    embed.add_field(
        name="👤 `!mytasks` `[jira_username]`",
        value=(
            "Xem chi tiết task của một người trong sprint hiện tại.\n"
            "Không truyền tham số → lấy task của bạn (dựa theo Discord ID).\n"
            "Ví dụ: `!mytasks linhdk@dxtech.vn`, `!mytasks datdt`"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔌 `!jira_status`",
        value="Kiểm tra kết nối tới Jira và đếm số task đang theo dõi.",
        inline=False,
    )
    embed.add_field(
        name="❓ `!help`",
        value="Hiển thị hướng dẫn này.",
        inline=False,
    )
    embed.add_field(
        name="⏰ Tự động nhắc hàng ngày",
        value=(
            f"Bot tự động gửi báo cáo sprint vào channel này mỗi ngày lúc "
            f"**{config.REMIND_CRON_HOUR:02d}:{config.REMIND_CRON_MINUTE:02d}** "
            f"(Thứ 2 – Thứ 6).\n"
            f"Nội dung bao gồm toàn bộ task đang mở trong sprint, nhóm theo trạng thái.\n"
            f"Cấu hình giờ nhắc qua biến môi trường `REMIND_CRON_HOUR` / `REMIND_CRON_MINUTE`."
        ),
        inline=False,
    )
    embed.set_footer(text="Jira Reminder Bot")
    await ctx.send(embed=embed)


@bot.command(name="remind", help="Gửi ngay báo cáo Jira vào channel và DM")
async def cmd_remind(ctx: commands.Context):
    await ctx.send("⏳ Đang lấy dữ liệu từ Jira...")
    await run_reminder(bot)
    await ctx.send("✅ Đã gửi xong!")


@bot.command(name="mytasks", help="Xem task Jira: !mytasks hoặc !mytasks <jira_username>")
async def cmd_mytasks(ctx: commands.Context, jira_username: str = None):
    from src.jira_client import JiraClient

    # Nếu không truyền username thì tự tra qua Discord ID
    if not jira_username:
        discord_user_id = str(ctx.author.id)
        jira_username = next(
            (jira for jira, did in config.JIRA_DISCORD_USER_MAP.items() if did == discord_user_id),
            None,
        )
        if not jira_username:
            await ctx.send("❌ Bạn chưa được map với tài khoản Jira nào. Dùng `!mytasks <jira_username>` để chỉ định.")
            return

    try:
        jira = JiraClient()
        loop = asyncio.get_event_loop()
        issues = await loop.run_in_executor(None, jira.get_my_issues, jira_username)
        if not issues:
            await ctx.send(f"✅ **{jira_username}** không có task nào trong sprint hiện tại!")
            return
        from src.notifier import build_detail_embeds
        for embed in build_detail_embeds(issues, jira_username):
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Lỗi: `{e}`")


@bot.command(name="priority", help="Báo cáo task theo priority: !priority hoặc !priority <Highest|High|Medium|Low|Lowest>")
async def cmd_priority(ctx: commands.Context, filter_priority: str = None):
    from src.jira_client import JiraClient
    from src.notifier import build_priority_embeds, PRIORITY_ORDER

    if filter_priority and filter_priority.capitalize() not in PRIORITY_ORDER:
        valid = ", ".join(f"`{p}`" for p in PRIORITY_ORDER)
        await ctx.send(f"❌ Priority không hợp lệ. Các giá trị hợp lệ: {valid}")
        return

    await ctx.send("⏳ Đang lấy dữ liệu từ Jira...")
    try:
        jira = JiraClient()
        loop = asyncio.get_event_loop()
        issues = await loop.run_in_executor(None, jira.get_active_sprint_issues)
        if filter_priority:
            issues = [i for i in issues if i.priority.lower() == filter_priority.lower()]
        for embed in build_priority_embeds(issues):
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Lỗi: `{e}`")


@bot.command(name="jira_status", help="Kiểm tra kết nối Jira")
async def cmd_jira_status(ctx: commands.Context):
    from src.jira_client import JiraClient
    try:
        jira = JiraClient()
        loop = asyncio.get_event_loop()
        issues = await loop.run_in_executor(None, jira.get_active_sprint_issues)
        await ctx.send(f"✅ Kết nối Jira OK — tìm thấy **{len(issues)}** issue đang theo dõi.")
    except Exception as e:
        await ctx.send(f"❌ Lỗi kết nối Jira: `{e}`")


if __name__ == "__main__":
    bot.run(config.DISCORD_BOT_TOKEN)
