import boto3, time
from botocore.exceptions import ClientError
from cloudwatch_utils import load_config, log_to_cw, send_cw_metric, load_state, save_state

def main():
    cfg = load_config('config.txt')
    region = cfg['REGION']
    ec2 = boto3.client('ec2', region_name=region)
    st = load_state()

    log_to_cw("Destroying infrastructure (Python)...", cfg)

    # Terminate instances
    iids = st.get('InstanceIds', [])
    if iids:
        ec2.terminate_instances(InstanceIds=iids)
        ec2.get_waiter('instance_terminated').wait(InstanceIds=iids)

    # Security group
    sg = st.get('SecurityGroupId')
    if sg:
        try:
            ec2.delete_security_group(GroupId=sg)
        except ClientError as e:
            print("SG delete:", e)

    # Route table (detach routes to IGW not needed; deleting IGW first is safer)
    # Better: delete associations (except main), then delete RTB
    rtb = st.get('RouteTableId')
    if rtb:
        try:
            assocs = ec2.describe_route_tables(RouteTableIds=[rtb])['RouteTables'][0].get('Associations', [])
            for a in assocs:
                if not a.get('Main'):
                    ec2.disassociate_route_table(AssociationId=a['RouteTableAssociationId'])
            # delete 0.0.0.0/0 route if exists (to detach IGW)
            try:
                ec2.delete_route(RouteTableId=rtb, DestinationCidrBlock='0.0.0.0/0')
            except ClientError:
                pass
            ec2.delete_route_table(RouteTableId=rtb)
        except ClientError as e:
            print("RTB delete:", e)

    # Internet gateway
    igw = st.get('InternetGatewayId')
    vpc = st.get('VpcId')
    if igw and vpc:
        try:
            ec2.detach_internet_gateway(InternetGatewayId=igw, VpcId=vpc)
        except ClientError:
            pass
        try:
            ec2.delete_internet_gateway(InternetGatewayId=igw)
        except ClientError as e:
            print("IGW delete:", e)

    # Subnets
    for sn in st.get('SubnetIds', []):
        try:
            ec2.delete_subnet(SubnetId=sn)
        except ClientError as e:
            print("Subnet delete:", e)

    # VPC
    if vpc:
        try:
            ec2.delete_vpc(VpcId=vpc)
        except ClientError as e:
            print("VPC delete:", e)

    send_cw_metric(1, cfg)
    log_to_cw("Infrastructure destroyed successfully", cfg)
    save_state({})  # clear

    print("Destroyed.")

if __name__ == "__main__":
    main()
