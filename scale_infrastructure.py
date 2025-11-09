import boto3
from cloudwatch_utils import load_config, log_to_cw, send_cw_metric, save_state, load_state

def main():
    cfg = load_config('config.txt')
    region = cfg['REGION']
    ec2 = boto3.client('ec2', region_name=region)
    state = load_state()

    log_to_cw("Scaling infrastructure: launching 1 extra instance", cfg)

    # Reuse subnet1 and SG from state
    subnet1 = state['SubnetIds'][0]
    sg = state['SecurityGroupId']

    # Find AMI again (safe if previous var lost)
    images = ec2.describe_images(
        Owners=[cfg['UBUNTU_OWNER']],
        Filters=[{'Name':'name','Values':[cfg['UBUNTU_FILTER']]}]
    )['Images']
    images.sort(key=lambda x: x['CreationDate'])
    ami = images[-1]['ImageId']

    user_data = '''#cloud-config
    runcmd:
      - apt-get update -y
      - apt-get install -y nginx
      - systemctl enable nginx
      - systemctl start nginx
    '''
    inst = ec2.run_instances(
        ImageId=ami, InstanceType=cfg['INSTANCE_TYPE'],
        MinCount=1, MaxCount=1,
        SecurityGroupIds=[sg],
        SubnetId=subnet1,
        UserData=user_data
    )['Instances'][0]['InstanceId']

    ec2.get_waiter('instance_running').wait(InstanceIds=[inst])
    ip = ec2.describe_instances(InstanceIds=[inst])['Reservations'][0]['Instances'][0].get('PublicIpAddress')

    state['InstanceIds'].append(inst)
    state['PublicIps'].append(ip)
    save_state(state)

    log_to_cw(f"Scaled: new instance {inst} ({ip})", cfg)
    send_cw_metric(1, cfg)
    print("Scaled with instance:", inst, ip)

if __name__ == "__main__":
    main()
