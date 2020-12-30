from aws_cdk import (
    core,
    aws_ecs as ecs,
    aws_logs as logs,
    aws_ec2 as ec2,
    aws_efs as efs
)

class MinebotStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # setup networking using default VPC
        self.vpc = ec2.Vpc.from_lookup(self, "VPC", is_default=True)
        self.init_sec_groups()

        # create cluster to hold instances (with Fargate this is more-or-less meaningless)
        self.cluster = ecs.Cluster(self, "MinecraftCluster", vpc=self.vpc)

        operator = 'Akemos_with_no_Q'
        name = 'cats-in-bread'
        guild = '786042802630950984'
        self.create_service(name, guild, operator, self.cluster)


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
    # Create a service with zero instances for the identified task (we'll start it on demand)
    #
    # Service will be tagged with the guild id so we can find it later
    #
    def create_service(self, name, guild, operator, cluster):
        service = ecs.FargateService(self, name + "-service", 
                                    cluster=self.cluster, 
                                    task_definition=self.create_task(name, guild, operator),
                                    assign_public_ip=True,
                                    desired_count=0,
                                    security_group=self.minecraft_sg,
                                    propagate_tags=ecs.PropagatedTagSource.SERVICE,
                                    platform_version=ecs.FargatePlatformVersion.VERSION1_4)
        core.Tags.of(service).add("guild", guild)
        return service

    def create_task(self, name, guild, operator):
        # define an ECS task
        task = ecs.FargateTaskDefinition(self, name, 
            cpu=1024, 
            memory_limit_mib=2048,
            volumes=[self.create_efs_volume(name)]
        )
        core.Tags.of(task).add("guild", guild)
        self.create_container(name, task, operator)
        return task

    def create_container(self, name, task, operator):
        # define the minecraft container
        container = task.add_container(
            name,
            image=ecs.ContainerImage.from_registry("itzg/minecraft-server"),
            essential=True,
            environment={
                "EULA": "TRUE", 
                "OPS": operator,
                "ALLOW_NETHER": "true",
                "ENABLE_COMMAND_BLOCK": "true",
                "MAX_TICK_TIME": "60000",
                "MAX_MEMORY": "1600M"
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix=name,
                log_retention=logs.RetentionDays.ONE_WEEK,
            )
        )
        container.add_port_mappings(ecs.PortMapping(container_port=25565))
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
