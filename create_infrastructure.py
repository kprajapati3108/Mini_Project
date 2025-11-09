import boto3, time, sys
from botocore.exceptions import ClientError
from cloudwatch_utils import load_config, log_to_cw, send_cw_metric, save_state, load_state

def latest_ubuntu_ami(ec2, owner, name_filter):
    images = ec2.describe_images(
        Owners=[owner],
        Filters=[{'Name':'name','Values':[name_filter]}]
    )['Images']
    images.sort(key=lambda x: x['CreationDate'])
    return images[-1]['ImageId']

def main():
    cfg = load_config('config.txt')
    region = cfg['REGION']
    ec2 = boto3.client('ec2', region_name=region)

    log_to_cw("=== Creating Infrastructure (Python) ===", cfg)

    # VPC
    vpc_id = ec2.create_vpc(CidrBlock=cfg['VPC_CIDR'])['Vpc']['VpcId']
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={'Value': True})

    # Subnets
    az_a = region + 'a'
    az_b = region + 'b'
    subnet1 = ec2.create_subnet(VpcId=vpc_id, CidrBlock=cfg['SUBNET_CIDR_1'], AvailabilityZone=az_a)['Subnet']['SubnetId']
    subnet2 = ec2.create_subnet(VpcId=vpc_id, CidrBlock=cfg['SUBNET_CIDR_2'], AvailabilityZone=az_b)['Subnet']['SubnetId']

    # IGW + Route
    igw = ec2.create_internet_gateway()['InternetGateway']['InternetGatewayId']
    ec2.attach_internet_gateway(InternetGatewayId=igw, VpcId=vpc_id)
    rtb = ec2.create_route_table(VpcId=vpc_id)['RouteTable']['RouteTableId']
    ec2.create_route(RouteTableId=rtb, DestinationCidrBlock='0.0.0.0/0', GatewayId=igw)
    ec2.associate_route_table(RouteTableId=rtb, SubnetId=subnet1)
    ec2.associate_route_table(RouteTableId=rtb, SubnetId=subnet2)

    # Security Group
    sg = ec2.create_security_group(
        GroupName='ITMO-444-544-lab-sg',
        Description='SSH & HTTP access',
        VpcId=vpc_id
    )['GroupId']
    # open 22 from current IP and 80 to all
    my_ip = boto3.client('sts').get_caller_identity()['Account']  # placeholder; cannot auto-detect IP without external call
    # Instead, allow 22 from anywhere for demo; tighten to your IP if desired
    ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[
        {'IpProtocol':'tcp','FromPort':22,'ToPort':22,'IpRanges':[{'CidrIp':'0.0.0.0/0'}]},
        {'IpProtocol':'tcp','FromPort':80,'ToPort':80,'IpRanges':[{'CidrIp':'0.0.0.0/0'}]},
    ])

    # AMI
    ami = latest_ubuntu_ami(ec2, cfg['UBUNTU_OWNER'], cfg['UBUNTU_FILTER'])

    # EC2 with user-data to install NGINX
    user_data = '''#cloud-config
    runcmd:
      - apt-get update -y
      - apt-get install -y nginx
      - systemctl enable nginx
      - systemctl start nginx
    '''
    instance = ec2.run_instances(
        ImageId=ami,
        InstanceType=cfg['INSTANCE_TYPE'],
        MinCount=1, MaxCount=1,
        SecurityGroupIds=[sg],
        SubnetId=subnet1,
        IamInstanceProfile={},
        TagSpecifications=[{
            'ResourceType':'instance',
            'Tags':[{'Key':'Name','Value':'itmo-mini-project'}]
        }],
        UserData=user_data,
    )['Instances'][0]['InstanceId']

    ec2.get_waiter('instance_running').wait(InstanceIds=[instance])
    desc = ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]
    public_ip = desc.get('PublicIpAddress')

    state = {
        'Region': region,
        'VpcId': vpc_id,
        'SubnetIds': [subnet1, subnet2],
        'InternetGatewayId': igw,
        'RouteTableId': rtb,
        'SecurityGroupId': sg,
        'InstanceIds': [instance],
        'PublicIps': [public_ip]
    }
    save_state(state)
    log_to_cw(f"EC2 instance created: {instance} ({public_ip})", cfg)
    send_cw_metric(1, cfg)
    print("Created. Public IP:", public_ip)

if __name__ == "__main__":
    main()
