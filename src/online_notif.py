from slack_sdk import WebClient
from src.read_data import get_token


def online_notif():
    client = WebClient(token=get_token("SLACK_BOT_TOKEN"))
    client.chat_postMessage(
        channel="U05RBU0RF4J",
        text="Cloud ChatOps is online.",
    )
