import base64
import json
import os
import time
import pytz
from datetime import datetime
from traceback import format_exc
from typing import List, Dict

import boto3

autoscaling_client = boto3.client("autoscaling")
rds_client = boto3.client("rds")
auth_user_name = os.environ.get("AUTH_USER_NAME")
auth_password = os.environ.get("AUTH_PASSWORD")


def convert_tz(naive_dt, from_tz, to_tz):
    localized = from_tz.localize(naive_dt)
    return localized.astimezone(to_tz)


def utc_hour_to_ams(hour: int) -> int:
    dt_ams = convert_tz(
        datetime.now().replace(hour=hour), pytz.utc, pytz.timezone("Europe/Amsterdam")
    )
    return dt_ams.hour


def ams_hour_to_utc(hour: int) -> int:
    dt_utc = convert_tz(
        datetime.now().replace(hour=hour), pytz.timezone("Europe/Amsterdam"), pytz.utc
    )
    return dt_utc.hour


def get_manual_scale_radios(current, max, min):
    inputs = []
    for scale in range(min, max + 1):
        if scale == current:
            inputs.append(
                f"""
            <input type="radio" id="scale-{scale}" checked="checked" name="scale" value="{scale}">
            <label for="scale-{scale}">{scale}</label><br>
            """
            )
        else:
            inputs.append(
                f"""
            <input type="radio" id="scale-{scale}" name="scale" value="{scale}">
            <label for="scale-{scale}">{scale}</label><br>
            """
            )
    return inputs


def get_input_box(box_id: str, box_label: str, current_value) -> str:
    return f"""
    <label for="{box_id}">{box_label}:</label>
    <input type="text" id="{box_id}" name="{box_id}" value="{current_value}">
    """


def get_hour_from_cron_line(cron_line: str) -> int:
    hour = int(cron_line.split(" ")[1])
    return utc_hour_to_ams(hour)


def get_scheduled_scale_input(schedule_actions: List[Dict]) -> List[str]:
    for action in schedule_actions:
        action_name = action["ScheduledActionName"]
        action_hour = get_hour_from_cron_line(action["Recurrence"])
        yield f"""
        <h3>{action_name.replace("-", " ")}</h3><br>
        {get_input_box(action_name + "-hour", "Hour", action_hour)}<br>
        {get_input_box(action_name + "-capacity", "Desired Size", action['DesiredCapacity'])}<br>
        """.strip()


def generate_form(min, max, current, schedule_actions):
    manual_inputs = get_manual_scale_radios(current, max, min)
    scheduled_inputs = list(get_scheduled_scale_input(schedule_actions))
    return f"""
    <!DOCTYPE html>
    <html>
    <body>
    
    <h2>Scale</h2>
    
    <form>
      <h3>Current Desired Scale</h3> 
      {"".join(manual_inputs)} <br>
      {"".join(scheduled_inputs)}
      <input type="submit" value="Submit">
    </form> 
    
    </body>
    </html>
    """


def extract_scale_actions_from_qry(query_params: Dict) -> Dict:
    output = {}
    for ky, vl in query_params.items():
        if ky.endswith("-capacity"):
            group_name = ky[:-9]
            if group_name not in output:
                output[group_name] = {}
            output[group_name]["capacity"] = int(vl)
        elif ky.endswith("-hour"):
            group_name = ky[:-5]
            if group_name not in output:
                output[group_name] = {}
            output[group_name]["hour"] = ams_hour_to_utc(int(vl))

    return output


def extract_existing_scale_actions(schedule_actions: List[Dict]) -> Dict:
    return {action["ScheduledActionName"]: action for action in schedule_actions}


def replace_hour_in_cron_line(existing_cron_line, hour) -> str:
    items = existing_cron_line.split(" ")
    items[1] = str(hour)
    return " ".join(items)


def return_html(html_str, status_code=200, headers=None):
    headers_result = {
        "Content-Type": "text/html",
        "Access-Control-Allow-Origin": "*",
    }
    if headers:
        headers_result.update(headers)

    return {
        "statusCode": status_code,
        "headers": headers_result,
        "body": html_str,
        "isBase64Encoded": False,
    }


def handler(event, context):
    print(json.dumps(event))
    authorization_header = {
        k.lower(): v
        for k, v in event["headers"].items()
        if k.lower() == "authorization"
    }
    if header := authorization_header.get("authorization"):
        auth_header_b64 = header.split()[1]
        auth_header_decoded = base64.standard_b64decode(auth_header_b64).decode("utf-8")
        request_username, request_password = auth_header_decoded.split(":")
        if request_username != auth_user_name or request_password != auth_password:
            return please_log_in()
    else:
        return please_log_in()
    try:
        query_params = event.get("queryStringParameters", {})
        desired_scale = query_params.get("scale", None)
        if desired_scale is not None:
            desired_scale = int(desired_scale)
            autoscaling_client.update_auto_scaling_group(
                AutoScalingGroupName=os.environ["ASG_NAME"],
                DesiredCapacity=desired_scale,
            )
            check_to_set_scale_tag_on_rds(desired_scale)
            scale_actions = extract_scale_actions_from_qry(query_params)
            asg_schedule_response = autoscaling_client.describe_scheduled_actions(
                AutoScalingGroupName=os.environ["ASG_NAME"]
            )
            existing_scale_actions = extract_existing_scale_actions(
                asg_schedule_response["ScheduledUpdateGroupActions"]
            )
            for scale_action_name, requested_scale_action in scale_actions.items():
                existing_action = existing_scale_actions[scale_action_name]
                new_action = {
                    ky: vl
                    for ky, vl in existing_action.items()
                    if ky
                    in (
                        "AutoScalingGroupName",
                        "ScheduledActionName",
                        "MinSize",
                        "MaxSize",
                    )
                }
                new_action["Recurrence"] = replace_hour_in_cron_line(
                    existing_action["Recurrence"], requested_scale_action["hour"]
                )
                new_action["DesiredCapacity"] = requested_scale_action["capacity"]
                autoscaling_client.put_scheduled_update_group_action(**new_action)
            time.sleep(3)
            return {
                "statusCode": 302,
                "headers": {"Location": "/"},
                "body": json.dumps({}),
            }
        asg_response = autoscaling_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[os.environ["ASG_NAME"]]
        )
        asg_schedule_response = autoscaling_client.describe_scheduled_actions(
            AutoScalingGroupName=os.environ["ASG_NAME"]
        )
        asg = asg_response["AutoScalingGroups"][0]
        output = generate_form(
            min=asg["MinSize"],
            max=asg["MaxSize"],
            current=asg["DesiredCapacity"],
            schedule_actions=asg_schedule_response["ScheduledUpdateGroupActions"],
        )
        return return_html(output)
    except Exception:
        print(format_exc())
        return return_html("<html><body>Failed</body></html>")


def check_to_set_scale_tag_on_rds(desired_scale: int):
    """
    This can be used to set tags on your RDS clusters when desired scale = 0
    It wil remove that tag if the desired scale > 0
    This script doesn't control the "on" or "off" state of the RDS cluster.
    It only sets the tag.

    This is supposed to work together with the AWS Instance Scheduler
    """
    scale_down_clusters = os.environ.get(
        "RDS_SCALEDOWN_CLUSTER_ARNS", ""
    ).split(",")
    if scale_down_clusters:
        scaledown_tag = os.environ.get("RDS_SCALEDOWN_TAG", "Schedule")
        print(f"Setting scale down tag:{scaledown_tag} to:{scale_down_clusters}")
        for rds_cluster_arn in scale_down_clusters:
            key, value = scaledown_tag.split(":")
            if desired_scale > 0:
                tags_response = rds_client.add_tags_to_resource(
                    ResourceName=rds_cluster_arn,
                    Tags=[{"Key": key, "Value": value}],
                )
            else:
                tags_response = rds_client.remove_tags_from_resource(
                    ResourceName=rds_cluster_arn,
                    TagKeys=[key],
                )
            print(tags_response)


def please_log_in():
    return return_html(
        "<html><body>Please log in</body></html>",
        headers={"WWW-Authenticate": 'Basic realm="Manual Scaler"'},
        status_code=401,
    )
