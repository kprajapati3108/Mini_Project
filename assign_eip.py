import boto3, sys, json
from cloudwatch_utils import load_config, load_state, save_state, log_to_cw

def main():
    cfg = load_config('config.txt')
    st = load_state()
    region = cfg['REGION']
    ec2 = boto3.client('ec2', region_name=region)
    if not st.get('InstanceIds'):
        print("No instance in state")
        sys.exit(1)
    iid = st['InstanceIds'][0]
    alloc = ec2.allocate_address(Domain='vpc')
    ec2.associate_address(AllocationId=alloc['AllocationId'], InstanceId=iid)
    st['ElasticIpAllocationId'] = alloc['AllocationId']
    st['ElasticIp'] = alloc['PublicIp']
    save_state(st)
    log_to_cw(f"Elastic IP {alloc['PublicIp']} associated to {iid}", cfg)
    print("Elastic IP:", alloc['PublicIp'])

if __name__ == "__main__":
    main()

