# Copyright 2021 Google LLC. This software is provided as is, without
# warranty or representation for any use or purpose. Your use of it is
# subject to your agreement with Google.

"""
Cloud Function to send Slack Notifications when a GKE node pool auto-upgrades.

The main library the script uses is slack_sdk to send Slack notifications using
a webhook url.

Python 3.9.6 is used. The python version can be set using pyenv. More
information about pyenv is available at https://github.com/pyenv/pyenv.

The flow for the GKE node pool auto-upgrade to Slack notification is:
1. GKE node pool is auto-upgraded
2. GKE sends a notification to Pub/Sub topic
3. The notification to Pub/Sub topic triggers the Cloud Function
4. The Cloud Function sends a notification to Slack

To set this up, follow the directions
https://cloud.google.com/kubernetes-engine/docs/how-to/cluster-upgrade-notifications#enabling_upgrade_notifications
To summarize:
1. create the Pub/Sub topic
2. follow the directions to tie the Pub/Sub topic to the cluster's
--notifcation-config

You can verify the setup for the notifications is correct by upgrading a node
pool in the cluster following the directions at
https://cloud.google.com/kubernetes-engine/docs/how-to/cluster-upgrade-notifications#verifying_setup_for_notifications
This can be done safely by specifying the existing gke version as the one to
upgrade to. You may need to specify --zone or --region.

The documentation to enable Slack Notification sent by the Cloud Function that
is triggered by a Pub/Sub topic is at
https://cloud.google.com/kubernetes-engine/docs/tutorials/upgrade-notifications-via-slack.

The basic steps are:
 1. Create a webhook url for Slack
 2. Deploy the Cloud Function with --trigger-topic set to the Pub/Sub topic
created in a previous step. Note the --set-env-vars to set the SLACK_WEBHOOK_URL
environment variable for the Cloud Function. In this case the command to deploy
the cloud function is
gcloud functions deploy <function name> \
--entry-point main \
--runtime python39 \
--trigger-topic <topic name>\
--set-env-vars="SLACK_WEBHOOK_URL=<slack webhook url>"
"""


def is_allowed_type(pubsub_attributes: dict, allowed_type_urls: list) -> bool:
    """Determines whether the type_url for the Pub/Sub event is allowed to
    trigger a Slack message
    """
    if not allowed_type_urls:
        return True

    for url in allowed_type_urls:
        if pubsub_attributes['type_url'] == url:
            return True

    return False


def create_slack_message(data: str, pubsub_attributes: dict) -> str:
    """Creates the message that is sent to Slack. It starts with the message in
    decoded data in plain text. Then it uses code block to give the details of
    auto-upgrade.
    """
    text = data + "\n```"

    for key in pubsub_attributes:
        text = text + f"\n\t{key}: {pubsub_attributes[key]}"

    text = text + "\n```"
    return text


def main(event, context):
    """Main entrypoint for the Cloud Function..
    Args:
         event (dict):  The dictionary with data specific to this type of
                        event. The `@type` field maps to
                         `type.googleapis.com/google.pubsub.v1.PubsubMessage`.
                        The `data` field maps to the PubsubMessage data
                        in a base64-encoded string. The `attributes` field maps
                        to the PubsubMessage attributes if any is present.
         context (google.cloud.functions.Context): Metadata of triggering event
                        including `event_id` which maps to the PubsubMessage
                        messageId, `timestamp` which maps to the PubsubMessage
                        publishTime, `event_type` which maps to
                        `google.pubsub.topic.publish`, and `resource` which is
                        a dictionary that describes the service API endpoint
                        pubsub.googleapis.com, the triggering topic's name, and
                        the triggering event type
                        `type.googleapis.com/google.pubsub.v1.PubsubMessage`.
    Returns:
        None. The output is written to Slack.
    """
    import base64
    import os
    from slack_sdk import WebhookClient

    pubsub_attributes = event['attributes']
    slack_url = os.environ['SLACK_WEBHOOK_URL']
    allowed_type_urls = ['type.googleapis.com/google.container.v1beta1.UpgradeEvent']

    data = str(base64.b64decode(event['data']).decode('utf-8'))

    is_allowed = is_allowed_type(pubsub_attributes, allowed_type_urls)

    if is_allowed:
        webhook = WebhookClient(slack_url)
        slack_message = create_slack_message(data, pubsub_attributes)
        response = webhook.send(text=slack_message)
