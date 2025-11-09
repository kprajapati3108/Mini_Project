import os, time, json
import boto3
from botocore.exceptions import ClientError

def load_config(path='config.txt'):
    cfg = {}
    if os.path.exists(path):
        with open(path, 'r') as f:
            for line in f:
                line=line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k,v = line.split('=',1)
                cfg[k.strip()] = v.strip()
    return cfg

def cw_clients(region):
    logs = boto3.client('logs', region_name=region)
    cw = boto3.client('cloudwatch', region_name=region)
    sns = boto3.client('sns', region_name=region)
    ec2 = boto3.client('ec2', region_name=region)
    return logs, cw, sns, ec2

def _ensure_log_stream(region, log_group, log_stream):
    logs, *_ = cw_clients(region)
    try:
        logs.create_log_group(logGroupName=log_group)
    except ClientError as e:
        pass
    try:
        logs.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
    except ClientError as e:
        pass

def log_to_cw(message, cfg):
    if cfg.get('DISABLE_CW_LOGS','').lower() == 'true':
        print(f"[LogDisabled] {message}")
        return
    region = cfg['REGION']
    log_group = cfg['CW_LOG_GROUP']
    log_stream = cfg['CW_LOG_STREAM']
    try:
        _ensure_log_stream(region, log_group, log_stream)
        logs, *_ = cw_clients(region)
        ts = int(time.time() * 1000)
        logs.put_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            logEvents=[{'timestamp': ts, 'message': message}],
        )
        print(f"[CloudWatchLog] {message}")
    except ClientError as e:
        print(f"[LogFallback] {message} ({e.response.get('Error',{}).get('Code','')})")

def send_cw_metric(value, cfg):
    region = cfg['REGION']
    cw = boto3.client('cloudwatch', region_name=region)
    cw.put_metric_data(
        Namespace=cfg['CW_METRIC_NAMESPACE'],
        MetricData=[{
            'MetricName': cfg['CW_METRIC_NAME'],
            'Value': float(value)
        }]
    )
    print(f"[Metric] {cfg['CW_METRIC_NAMESPACE']}/{cfg['CW_METRIC_NAME']}={value}")

def save_state(obj, path='state/stack_state.json'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2)

def load_state(path='state/stack_state.json'):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)
