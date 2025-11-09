import boto3, json
from cloudwatch_utils import load_config, log_to_cw, send_cw_metric, load_state

def main():
    cfg = load_config('config.txt')
    region = cfg['REGION']
    cw = boto3.client('cloudwatch', region_name=region)
    disable_sns = cfg.get('DISABLE_SNS','').lower() == 'true'
    topic_arn = None
    if not disable_sns:
        sns = boto3.client('sns', region_name=region)
        topic_arn = sns.create_topic(Name=cfg['SNS_TOPIC_NAME'])['TopicArn']
        sns.subscribe(TopicArn=topic_arn, Protocol='email', Endpoint=cfg['ALARM_EMAIL'])
        log_to_cw(f"SNS Topic created: {topic_arn}", cfg)
    send_cw_metric(1, cfg)
    alarm_args = dict(
        AlarmName=cfg['ALARM_NAME'],
        MetricName=cfg['CW_METRIC_NAME'],
        Namespace=cfg['CW_METRIC_NAMESPACE'],
        Statistic='Sum',
        Period=300,
        Threshold=0.0,
        ComparisonOperator='LessThanThreshold',
        EvaluationPeriods=1
    )
    if not disable_sns and topic_arn:
        alarm_args['AlarmActions'] = [topic_arn]
    cw.put_metric_alarm(**alarm_args)
    log_to_cw(f"CloudWatch Alarm created: {cfg['ALARM_NAME']}", cfg)
    st = load_state()
    instance_ids = st.get('InstanceIds', [])
    widgets = []
    for iid in instance_ids:
        widgets.append({
          "type":"metric",
          "properties":{
            "title": f"CPUUtilization {iid}",
            "metrics":[["AWS/EC2","CPUUtilization","InstanceId",iid]],
            "view":"timeSeries",
            "region": region,
            "stat":"Average",
            "period": 300
          }
        })
        widgets.append({
          "type":"metric",
          "properties":{
            "title": f"NetworkIn/Out {iid}",
            "metrics":[
              ["AWS/EC2","NetworkIn","InstanceId",iid],
              ["AWS/EC2","NetworkOut","InstanceId",iid]
            ],
            "view":"timeSeries",
            "region": region,
            "stat":"Sum",
            "period": 300
          }
        })
    widgets.append({
      "type":"metric",
      "properties":{
        "title":"Custom: StepsCompleted",
        "metrics":[[cfg['CW_METRIC_NAMESPACE'], cfg['CW_METRIC_NAME']]],
        "view":"timeSeries",
        "region": region,
        "stat":"Sum",
        "period": 300
      }
    })
    dashboard_body = json.dumps({"widgets": widgets})
    cw.put_dashboard(DashboardName="InfraAutomationDashboard", DashboardBody=dashboard_body)
    log_to_cw("CloudWatch Dashboard created: InfraAutomationDashboard", cfg)
    print("Monitoring set. Visit CloudWatch > Dashboards > InfraAutomationDashboard")

if __name__ == "__main__":
    main()
