#!/usr/bin/env python3
import os

from aws_cdk import core

from minebot.minebot_stack import MinebotStack

app = core.App()
env_sydney = core.Environment(account=os.getenv("AWS_ACCOUNT", "964583318248"), 
                              region=os.getenv("AWS_REGION", "ap-southeast-2"))
MinebotStack(app, "minebot", env=env_sydney)

app.synth()
