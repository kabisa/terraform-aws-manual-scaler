import base64
import json
import os
import time
from traceback import format_exc

import boto3

client = boto3.client("autoscaling")
auth_user_name = os.environ.get("AUTH_USER_NAME")
auth_password = os.environ.get("AUTH_PASSWORD")


def generate_form(min, max, current):
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

    return f"""
    <!DOCTYPE html>
    <html>
    <body>
    
    <h2>Scale</h2>
    
    <form>
      {"".join(inputs)}
      <input type="submit" value="Submit">
    </form> 
    
    </body>
    </html>
    """


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
    authorization_header = {k.lower(): v for k, v in event['headers'].items() if k.lower() == 'authorization'}
    if header := authorization_header.get('authorization'):
        auth_header_b64 = header.split()[1]
        auth_header_decoded = base64.standard_b64decode(auth_header_b64).decode('utf-8')
        request_username, request_password = auth_header_decoded.split(':')
        if request_username != auth_user_name or request_password != auth_password:
            return please_log_in()
    else:
        return please_log_in()
    try:
        desired_scale = event.get("queryStringParameters", {}).get("scale", None)
        if desired_scale is not None:
            client.update_auto_scaling_group(
                AutoScalingGroupName=os.environ["ASG_NAME"],
                DesiredCapacity=int(desired_scale),
            )
            time.sleep(3)
            return {
                "statusCode": 302,
                "headers": {"Location": "/"},
                "body": json.dumps({})
            }
        asg_response = client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[
                os.environ["ASG_NAME"],
            ]
        )
        asg = asg_response["AutoScalingGroups"][0]
        output = generate_form(
            min=asg["MinSize"], max=asg["MaxSize"], current=asg["DesiredCapacity"]
        )
        return return_html(output)
    except Exception:
        print(format_exc())
        return return_html("<html><body>Failed</body></html>")


def please_log_in():
    return return_html(
        "<html><body>Please log in</body></html>",
        headers={
            "WWW-Authenticate": 'Basic realm="Manual Scaler"'
        },
        status_code=401
    )
