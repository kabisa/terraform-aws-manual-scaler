import json
import os
import time
from traceback import format_exc

import boto3

client = boto3.client("autoscaling")


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


def handler(event, context):
    print(json.dumps(event))
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
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html",
                "Access-Control-Allow-Origin": "*",
            },
            "body": output,
            "isBase64Encoded": False,
        }
    except Exception:
        print(format_exc())
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html",
                "Access-Control-Allow-Origin": "*",
            },
            "body": "<html><body>Failed</body></html>",
            "isBase64Encoded": False,
        }

