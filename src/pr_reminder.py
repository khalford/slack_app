from typing import List, Dict
from datetime import datetime, timedelta
from read_data import get_token, get_user_map, get_repos
from get_github_prs import GetGitHubPRs
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class PostPRsToSlack:
    """
    This class handles the Slack posting.
    """

    def __init__(self):
        super().__init__()
        self.repos = get_repos()
        self.client = WebClient(token=get_token("SLACK_BOT_TOKEN"))
        self.slack_ids = get_user_map()
        self.prs = GetGitHubPRs(get_repos()).run()
        self.CHANNEL = "temp-chatops"

    def run_public(self, mention, channel=None) -> None:
        """
        This method calls the functions to post the reminder message and subsequent PR messages.
        :param channel: Changes the channel to post the messages to.
        :param mention: To mention the users in Slack or just post their name.
        """
        if channel:
            self.CHANNEL = channel
        reminder_message = self.post_reminder_message()
        self.post_thread_messages(self.prs, reminder_message, mention)

    def post_reminder_message(self) -> WebClient.chat_postMessage:
        """
        This method posts the main reminder message to start the thread if PR notifications.
        :return: The reminder message return object
        """
        reminder = self.client.chat_postMessage(
            channel=self.CHANNEL,
            text="Here are the outstanding PRs as of today:",
        )
        return reminder

    def post_thread_messages(
        self,
        prs: Dict[str, List],
        reminder_message: WebClient.chat_postMessage,
        mention: bool,
    ) -> None:
        """
        This method collates each individual PR reminder message and calls a post method.
        :param mention: To mention the users or not
        :param prs: A list of PRs from GitHub
        :param reminder_message: The reminder message object
        """
        for repo in prs.values():
            for pr in repo:
                info = {
                    "pr_title": f"{pr['title']} #{pr['number']}",
                    "user": pr["user"]["login"],
                    "url": pr['html_url'],
                    "created_at": pr['created_at'],
                    "channel": reminder_message.data["channel"],
                    "thread_ts": reminder_message.data["ts"],
                    "mention": mention,
                    "draft": pr['draft'],
                }
                checked_info = self.check_pr(info)
                self.send_thread(**checked_info)

    def check_pr(self, info: Dict) -> Dict:
        if info['user'] not in self.slack_ids:
            info['user'] = 'U01JG0LKU3W'
        else:
            info['user'] = self.get_username(info['user'])
        opened_date = datetime.fromisoformat(info['created_at']).replace(tzinfo=None)
        datetime_now = datetime.now().replace(tzinfo=None)
        time_cutoff = datetime_now - timedelta(days=30*6)
        if opened_date < time_cutoff:
            info['old'] = True
        del info['created_at']
        return info

    def send_thread(self, pr_title: str, user: str, url: str, channel: str, thread_ts: str, mention: bool, draft=False, old=False) -> None:
        message = self.construct_message(pr_title, user, url, mention, draft, old)
        response = self.client.chat_postMessage(
            text=message, channel=channel, thread_ts=thread_ts, unfurl_links=False
        )
        assert response["ok"]
        reactions = {
            "old": old,
            "draft": draft,
        }
        self.send_thread_react(channel, response.data['ts'], reactions)

    def send_thread_react(self, channel: str, ts: str, reactions: Dict) -> None:
        mapping = {
            "old": "alarm_clock",
            "draft": "scroll",
        }
        for react in reactions:
            if reactions[react]:
                react_response = self.client.reactions_add(channel=channel, name=mapping[react], timestamp=ts)
                assert react_response["ok"]

    def construct_message(self, pr_title: str, user: str, url: str, mention: bool, draft: bool, old: bool):
        message = ["", "", "", "", ""]
        if old:
            message[0] = "*This PR is older than 6 months. Consider closing it:*"
        message[1] = f"Pull Request: <{url}|{pr_title}>"
        if mention and not draft:
            message[2] = f"Author: <@{user}>"
        else:
            name = self.get_real_name(user)
            message[2] = f"Author: {name}"
        for i in message:
            if not i:
                message.pop(message.index(i))
        message_construction = '\n'.join(message)
        return message_construction

    def get_real_name(self, username: str) -> str:
        """
        This method uses the Slack client method to get the real name of a user and returns it.
        :param username: The user ID to look for
        :return: Returns the real name or if not found the name originally parsed in
        """
        try:
            name = self.client.users_profile_get(user=username)["profile"]["real_name"]
        except SlackApiError:
            name = username
        return name

    def get_username(self, user: str) -> str:
        """
        This method checks if we have a Slack id for the GitHub user and returns it.
        :param user: GitHub username to check for
        :return: Slack ID or GitHub username
        """
        if user in self.slack_ids:
            return self.slack_ids[user]
        return user