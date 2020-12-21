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

        # setup networking
        mc_vpc = ec2.Vpc(self, "minecraft-vpc", 
                        max_azs=2, # 2 is enough
                        nat_gateways=0, # don't want any NAT gateways
                        subnet_configuration=[ # public subnets only, don't need private
                            ec2.SubnetConfiguration(name="minecraft-pub", subnet_type=ec2.SubnetType.PUBLIC)
                        ])
        mc_sg = ec2.SecurityGroup(self, 'minecraft-sg', 
            vpc=mc_vpc,
            allow_all_outbound=True,
            description='minecraft security group'
        )
        mc_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(25565), 'Allow minecraft from anywhere')
        efs_sg = ec2.SecurityGroup(self, 'efs-sg',
            vpc=mc_vpc,
            description='EFS security group'
        )
        efs_sg.add_ingress_rule(mc_sg, ec2.Port.tcp(2049), 'Allow EFS clients')
        mc_sg.add_ingress_rule(efs_sg, ec2.Port.tcp(2049), 'Allow EFS access')

        # create an EFS filesystem
        fs = efs.FileSystem(self, 'minecraft-fs', 
                            vpc=mc_vpc,
                            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
                            throughput_mode=efs.ThroughputMode.BURSTING,
                            security_group=efs_sg
        )
        fs.add_access_point("cats-in-bread", path="/")

        # define an ECS volume for this filesystem
        mc_volume = ecs.Volume(
            name="cats-in-bread",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=fs.file_system_id, 
                # root_directory="/cats_in_bread"
            )
        )

        # create an ECS task
        minecraft = ecs.FargateTaskDefinition(self, "minecraft", 
            cpu=1024, 
            memory_limit_mib=2048,
            volumes=[mc_volume]
        )

        # add the minecraft container
        mc_container = minecraft.add_container(
            "minecraft",
            image=ecs.ContainerImage.from_registry("itzg/minecraft-server"),
            essential=True,
            environment={
                "EULA": "TRUE", 
                "OPS": "Akemos_with_no_Q",
                "ALLOW_NETHER": "true",
                "ENABLE_COMMAND_BLOCK": "true",
                "MAX_TICK_TIME": "60000",
                "MAX_MEMORY": "1600M"
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="minecraft",
                log_retention=logs.RetentionDays.ONE_WEEK,
            )
        )
        mc_container.add_port_mappings(ecs.PortMapping(container_port=25565))
        # mount the EFS volume on the container
        mc_container.add_mount_points(ecs.MountPoint(
                                        container_path="/data", 
                                        source_volume=mc_volume.name, 
                                        read_only=False)
        )

        # create a service with 0 instances
        mc_cluster = ecs.Cluster(self, "MinecraftCluster", vpc=mc_vpc)
        mc_service = ecs.FargateService(self, "minecraft-service", 
                                    cluster=mc_cluster, 
                                    task_definition=minecraft,
                                    assign_public_ip=True,
                                    desired_count=0,
                                    security_group=mc_sg,
                                    platform_version=ecs.FargatePlatformVersion.VERSION1_4
        )
