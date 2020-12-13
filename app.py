#!/usr/bin/env python3

from aws_cdk import core

from minebot.minebot_stack import MinebotStack


app = core.App()
MinebotStack(app, "minebot")

app.synth()
