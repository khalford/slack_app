from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from src.pr_reminder import PostPRsToSlack
from src.read_data import get_token
from src.post_to_influx import PostDataToInflux
from src.online_notif import online_notif
import logging
import schedule

logging.basicConfig(level=logging.DEBUG)
app = AsyncApp(token=get_token("SLACK_BOT_TOKEN"))


@app.command("/prs")
async def remind_prs(ack, respond, command):
    async def command_pr(context):
        channel = context["user_id"]
        PostPRsToSlack().run(channel=channel, mention=None)

    await ack()
    await respond("Check out your DMs.")
    await command_pr(command)


async def schedule_jobs():
    def run_pr(channel, mention=False):
        PostPRsToSlack().run_public(mention=mention, channel=channel)

    def post_data():
        PostDataToInflux().run()

    schedule.every().monday.at("09:00").do(
        run_pr, mention=True, channel="pull-requests"
    )
    schedule.every().wednesday.at("09:00").do(run_pr, channel="pull-requests")
    schedule.every().friday.at("09:00").do(run_pr, channel="pull-requests")

    schedule.every().day.at("09:00").do(post_data)

    online_notif()
    while True:
        schedule.run_pending()
        await asyncio.sleep(10)


async def main():
    asyncio.ensure_future(schedule_jobs())
    handler = AsyncSocketModeHandler(app, get_token("SLACK_APP_TOKEN"))
    await handler.start_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
