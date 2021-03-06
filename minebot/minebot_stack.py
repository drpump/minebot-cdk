from aws_cdk import (
    core,
    aws_ecs as ecs,
    aws_logs as logs,
    aws_ec2 as ec2,
    aws_efs as efs,
    aws_iam as iam
)
import json, os
class MinebotStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # setup networking using default VPC
        self.vpc = ec2.Vpc.from_lookup(self, "VPC", is_default=True)
        self.init_sec_groups()
        self.init_bot_group()

        # create cluster to hold instances (with Fargate this is more-or-less meaningless)
        self.cluster = ecs.Cluster(self, "MinecraftCluster", vpc=self.vpc)

        # create ECS services for the specified guilds
        for guild in self.load_config():
            self.create_service(guild['name'], guild['id'], guild['ops'], guild['type'])

    #
    # Load configuration file
    #
    def load_config(self):
        if "MINEBOT_CONFIG" in os.environ:
            with open(os.environ["MINEBOT_CONFIG"], "r") as conf_file:
                conf = json.load(conf_file)
                if type(conf) is list and len(conf) > 0:
                    return conf
                else:
                    print(f"Conf type: {type(conf).__name__} length: {str(len(conf))}, content: {str(conf)}")
                    raise Exception('Expected json list of discord guilds in file identified by MINEBOT_CONFIG. Invalid or empty list detected')
        else: 
            raise Exception('Requires environment variable MINEBOT_CONFIG to identify config file')

    #
    # Create security groups required for servers and an ssh utility container
    #
    def init_sec_groups(self):
        self.efs_sg = ec2.SecurityGroup(self, 'efs-sg',
            vpc=self.vpc,
            description='EFS security group'
        )
        self.minecraft_sg = self.efs_sec_group('minecraft', 25565)
        self.ssh_sg = self.efs_sec_group('ssh', 22)
        return

    #
    # Create a security group for access to specified port and efs filesystems
    #
    def efs_sec_group(self, name, port):
        sec_group = ec2.SecurityGroup(self, name + '-sg', 
            vpc=self.vpc,
            allow_all_outbound=True,
            description=name + ' security group'
        )
        sec_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(port), name + ' from anywhere')

        self.efs_sg.add_ingress_rule(sec_group, ec2.Port.tcp(2049), 'Allow clients from ' + name)
        sec_group.add_ingress_rule(self.efs_sg, ec2.Port.tcp(2049), 'Allow efs access for ' + name)

        return sec_group

    #
    # Create an IAM group with associated policy for the bot to access start/stop/state in ECS
    #
    def init_bot_group(self):
        statement = iam.PolicyStatement(effect = iam.Effect.ALLOW)
        statement.add_actions("ecs:ListClusters", 
                              "ecs:ListServices", 
                              "ecs:DescribeServices", 
                              "ecs:ListTasks", 
                              "ecs:DescribeTasks", 
                              "ecs:UpdateService",
                              "ec2:DescribeNetworkInterfaces")
        statement.add_all_resources()
        group = iam.Group(self, "minebot-group")
        group.add_managed_policy(iam.ManagedPolicy(self, "minebot-start-stop-policy", statements=[statement]))
        return group

    #
    # Create a service for the guild with zero instances (we'll start it on demand)
    #
    def create_service(self, name, guild, operators, type):
        service = ecs.FargateService(self, name + "-service", 
                                    cluster=self.cluster, 
                                    task_definition=self.create_task(name, guild, operators, type),
                                    assign_public_ip=True,
                                    desired_count=0,
                                    security_group=self.minecraft_sg,
                                    propagate_tags=ecs.PropagatedTagSource.SERVICE,
                                    platform_version=ecs.FargatePlatformVersion.VERSION1_4)
        # guild tag allows us to find it easily for stop/start
        core.Tags.of(service).add("guild", guild)
        return service

    #
    # Create an ECS task for the specified guild
    #
    def create_task(self, name, guild, operators, type):
        # define an ECS task
        volume = self.create_efs_volume(name)
        task = ecs.FargateTaskDefinition(self, name, 
            cpu=2048, 
            memory_limit_mib=4096,
            volumes=[volume]
        )
        core.Tags.of(task).add("guild", guild)
        self.create_container(name, task, operators, volume, type)
        return task

    #
    # Create a container for our minecraft image with mount point for the specified volume
    #
    def create_container(self, name, task, operators, volume, type="VANILLA"):
        container = task.add_container(
            name,
            image=ecs.ContainerImage.from_registry("itzg/minecraft-server"),
            essential=True,
            environment={
                "EULA": "TRUE", 
                "OPS": operators,
                "ALLOW_NETHER": "true",
                "ENABLE_COMMAND_BLOCK": "true",
                "MAX_TICK_TIME": "60000",
                "MAX_MEMORY": "3600M",
                "TYPE": type
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix=name,
                log_retention=logs.RetentionDays.ONE_WEEK,
            )
        )
        container.add_port_mappings(ecs.PortMapping(container_port=25565))
        container.add_mount_points(ecs.MountPoint(
                                    container_path="/data", 
                                    source_volume=volume.name, 
                                    read_only=False))
        return container

    #
    # Create an efs volume to mount on a container
    #
    def create_efs_volume(self, name):
        # create an EFS filesystem and access point
        fs = efs.FileSystem(self, name + '-fs', 
                            vpc=self.vpc,
                            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
                            throughput_mode=efs.ThroughputMode.BURSTING,
                            security_group=self.efs_sg
        )
        fs.add_access_point(name, path="/")
        # define an ECS volume for this filesystem
        volume = ecs.Volume(
            name=name + '-volume',
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=fs.file_system_id
            )
        )
        return volume
