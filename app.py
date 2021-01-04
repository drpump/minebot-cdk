#!/usr/bin/env python3
import os

from aws_cdk import core

from minebot.minebot_stack import MinebotStack

app = core.App()
env = core.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"], 
                       region=os.environ["CDK_DEFAULT_REGION"])
MinebotStack(app, "minebot", env=env)

app.synth()
