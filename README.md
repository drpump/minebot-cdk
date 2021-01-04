
# Create minecraft ECS services

This AWS CDK project contains a CDK stack definition to create ECS (dockerized) minecraft 
servers using persistent EFS filesystems to hold the worlds and their configuration.

Features:
* ECS services are initially created with a `desiredCount` of 0 meaning they won't incur 
  any charges until you explicitly start them
* Each service has a separate EFS filesystem so that worlds are persisted across restarts,
  noting that there are storage charges for EFS filesystem volumes
* The docker image (from https://hub.docker.com/itzg/minecraft-server) downloads the latest
  minecraft version when started so you always have the latest
* Services are tagged with a discord guild/server id from the config file so that they
  can be started from a discord server using my discord bot
* An IAM group for starting and stopping the services is created, allowing you to create 
  a least-privileges IAM user to start and stop minecraft
* Each service is created with a CloudWatch log group so that you can monitor them.
  Logs are configured for deletion after 7 days, noting that there are storage charges for logs.

To use:

1. `cp minebot-config.json.sample minebot-config.json`
1. Set the `MINEBOT_CONFIG` environment variable to point at your config file, e.g. `export MINEBOT_CONFIG=${PWD}/minebot-config.json` (bash)
1. Edit the config with details of your discord guilds (id == discord server/guild id) and minecraft operator usernames. If you don't have a discord guild/server just use any string as the id.
1. If you don't already have a the AWS cli installed and configured, install it and run `aws configure` to configure your default account and region details
1. If you don't already have the AWS cdk cli installed, install it
1. Follow the CDK instructions below to create and deploy the stack to your AWS account
1. Start your minecraft server(s) by updating the `desired count` to 1 via the AWS ECS console, then 
   copy the task public IP address to connect to your server
1. Stop your minecraft server(s) by updating the `desired count` to 0 via the AWS ECS console
1. To add more servers, add new guild entries to `minecraft-config.json` and re-run `cdk deploy`

Assuming this all works, you can also try running my discord bot and inviting it to your server. This
allows discord users on your servers to start/stop the minecraft server on demand. 

## CDK instructions
## Create Python virtualenv

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

### Create and deploy stack

At this point you can now synthesize the CloudFormation template for this code:

```
$ cdk synth
```

If this succeeds, then you can deploy:

```
$ cdk deploy
```

Enjoy!
