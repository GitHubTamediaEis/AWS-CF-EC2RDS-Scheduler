######################################################################################################################
#  Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           #
#                                                                                                                    #
#  Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance        #
#  with the License. A copy of the License is located at                                                             #
#                                                                                                                    #
#      http://aws.amazon.com/asl/                                                                                    #
#                                                                                                                    #   
#  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    #
#  and limitations under the License.                                                                                #
######################################################################################################################

import boto3
import datetime
import json
import time
from collections import defaultdict
import re
import pytz

#Default startTime, stopTime, TimeZone
defaultStartTime = 'none'
defaultStopTime = 'none'
defaultTimeZone = 'utc'
defaultDaysActive = 'all'

def putCloudWatchMetric(region, instance_id, instance_state):
    
    cw = boto3.client('cloudwatch')
    
    cw.put_metric_data(
        Namespace='EC2RDSScheduler',
        MetricData=[{
            'MetricName': instance_id,
            'Value': instance_state,

            'Unit': 'Count',
            'Dimensions': [
                {
                    'Name': 'Region',
                    'Value': region
                }
            ]
        }]
    )

def scheduler_action(tagValue):
    
    # Weekdays Interpreter
    weekdays = ['mon', 'tue', 'wed', 'thu', 'fri']
    
    # Monthdays Interpreter (1..31)
    monthdays = re.compile(r'^(0?[1-9]|[12]\d|3[01])$')
    
    # nth weekdays Interpreter
    nthweekdays=re.compile('\w{3}/\d{1}')
    
    # Split out Tag & Set Variables to default
    default1 = 'default'
    default2 = 'true'
    
    #Default scheduler action
    Action = 'None'
    
    ptag = tagValue.replace(':',';').split(";")
    
    # Get time values
    startTime = defaultStartTime
    stopTime = defaultStopTime
    timeZone = defaultTimeZone
    daysActive = defaultDaysActive
    
    # Valid timezone
    isValidTimeZone = True
    
    # Parse tag-value
    if len(ptag) >= 1:
        if ptag[0].lower() in (default1, default2):
            startTime = defaultStartTime
        else:
            startTime = ptag[0]
            stopTime = ptag[0]
            
    # Support 24x7
    if startTime  == '24x7':
        return "START"
        
    if len(ptag) >= 2:
        stopTime = ptag[1]
        
    if len(ptag) >= 3:
        #Timezone is case senstive
        timeZone = ptag[2]
        # timeZone is not empty and not DefaultTimeZone
        if timeZone != defaultTimeZone and timeZone != '':
            # utc is not included in pytz.all_timezones
            if timeZone != 'utc':
                if timeZone in pytz.all_timezones:
                    tz = pytz.timezone(timeZone)
                # No action if timeZone is not supported
                else:
                    print ("Invalid time zone :", timeZone)
                    isValidTimeZone = False
            # utc timezone
            else:
                tz = pytz.timezone('utc')
                
    if len(ptag) >= 4:
        daysActive = ptag[3].lower()
        
    isActiveDay = False
    
    # 24x5 support 
    if startTime  == '24x5':
       if nowDay == 'mon':
           startTime = defaultStartTime
           stopTime = 'none'
           isActiveDay = True
       elif nowDay == 'fri':
           isActiveDay = True
           startTime = 'none'
           stopTime = defaultStopTime
    elif daysActive == "all":
        isActiveDay = True
    elif daysActive == "weekdays":
        if (nowDay in weekdays):
            isActiveDay = True
    else:
        for d in daysActive.split(","):
            # mon, tue,wed,thu,fri,sat,sun ?
            if d.lower() == nowDay:
                    isActiveDay = True
            # Month days?
            elif monthdays.match(d):
                if int(d) == nowDate:
                     isActiveDay = True
            # mon/1 first Monday of the month
            # tue/2 second Tuesday of the month
            # Fri/3 third Friday of the month
            # sat/4 forth Saturday of the month
            elif nthweekdays.match(d):
                (weekday,nthweek) = d.split("/")
                if (weekday.lower() == nowDay) and ( nowDate >= (int(nthweek) * 7 - 6)) and (nowDate <= (int(nthweek) * 7)):
                   isActiveDay = True
                   
    # Should instance be started?
    if startTime >= str(nowMax) and startTime <= str(now) and isActiveDay == True and isValidTimeZone == True:
        Action = "START"
    
    # Should instance be stopped?    
    if stopTime >= str(nowMax) and stopTime <= str(now) and isActiveDay == True and isValidTimeZone == True:
        Action = "STOP"
        
    return Action

def lambda_handler(event, context):
    
    print ("* EC2 and RDS Scheduler started")
    
    # Define global variables
    global defaultStartTime
    global defaultStopTime
    global defaultTimeZone
    global defaultDaysActive
    global Schedule
    global now
    global nowMax
    global tz
    global nowDay
    global nowDate
    
    ## Set global default values from CloudWatch Rule Input event
    # Customized time values
    defaultStartTime = event['DefaultStartTime'].replace("'","")
    defaultStopTime = event['DefaultStopTime'].replace("'","")
    defaultTimeZone = event['DefaultTimeZone']
    defaultDaysActive = event['DefaultDaysActive']
    
    # Default Timzone
    tz = pytz.timezone(defaultTimeZone)
    
    # Customized tag name
    customTagName = event['CustomTagName']
    customTagLen = len(customTagName)
    createMetrics = event['CloudWatchMetrics']
    ASGSupport = event['ASGSupport']
    
    # Customized RDS tag name
    RDSSupport = event['RDSSupport']
    customRDSTagName = event['CustomRDSTagName']
    customRDSTagLen = len(customRDSTagName)
    
    # Set time/day variables
    now = datetime.datetime.now(tz).strftime("%H%M")
    
     # Get schedule to know what timerange to cover
    scheduleDict =	{
      "5minutes": 4,
      "15minutes": 14,
      "30minutes": 29,
      "1hour": 59
    }
    Schedule = scheduleDict[event['Schedule']]
    
    # Set nowMax to now minus schedule
    if  datetime.datetime.now(tz).strftime("%H") != '00':
        nowMax = datetime.datetime.now(tz) - datetime.timedelta(minutes=Schedule)
        nowMax = nowMax.strftime("%H%M")
    else:
        nowMax = "0000"
        
    # Set day and date
    nowDay = datetime.datetime.now(tz).strftime("%a").lower()
    nowDate = int(datetime.datetime.now(tz).strftime("%d"))
    
    # Create connection to the EC2 using Boto3 client interface
    ec2 = boto3.client('ec2')
    
    # Set regions
    if event['Regions'] == 'all':
        AwsRegionNames = []
        for r in ec2.describe_regions()['Regions']:
            AwsRegionNames.append(r['RegionName'])
    else:
        AwsRegionNames = event['Regions'].split(",")
        
    print ("Operate in regions: ", " ".join(AwsRegionNames))
    
    # RDS support?
    if RDSSupport == "Yes":
        print ("RDS support is enabled")
    else:
        print ("RDS support is disabled")
        
    # ASG support?
    if ASGSupport == "Yes":
        print ("ASG support is enabled")
    else:
        print ("ASG support is disabled")
        
    # Loop through regions
    for region_name in AwsRegionNames:
        try:
            
            print ("**", region_name)
            
            # Declare lists and dicts
            startList = []
            stopList = []
            
            if ASGSupport == "Yes":
                InServiceList = defaultdict(list)
                StandbyList = defaultdict(list)
                
            # Create connection to the EC2 using Boto3 resources interface
            ec2 = boto3.resource('ec2', region_name = region_name)
            
            # List all instances
            instances = ec2.instances.all()
            
            if ASGSupport == "Yes":
                # Create connection to Autoscaling using Boto3 client interface
                aws_scaling_client = boto3.client('autoscaling', region_name = region_name)
                
                # List all instances in ASGs
                next_token = ''
                while next_token is not None:
                    if next_token is not '':
                        describe_result = aws_scaling_client.describe_auto_scaling_instances(NextToken=next_token)
                        
                    else:
                        describe_result = aws_scaling_client.describe_auto_scaling_instances()
                    next_token = describe_result.get('NextToken')
                    
                asgmembers = describe_result.get('AutoScalingInstances')
                
            print ("*** Populate EC2 lists")
            
            for i in instances:
                # Search tag
                if i.tags != None:
                    for t in i.tags:
                        if t['Key'][:customTagLen] == customTagName:
                            # Get instance state
                            state = i.state['Name']
                            
                            # Post current state of the instance
                            if createMetrics == "Yes":
                                if state == "running":
                                    putCloudWatchMetric(region_name, i.instance_id, 1)
                                if state == "stopped":
                                    putCloudWatchMetric(region_name, i.instance_id, 0)
                                    
                            # Get action for instance
                            action = scheduler_action(tagValue = t['Value'])
                            
                            # Append to start list
                            if action == "START" and state == "stopped":
                                if i.instance_id not in startList:
                                    startList.append(i.instance_id)
                                    print (i.instance_id, "with tag", t['Value'], "added to START list")
                                    
                                    if ASGSupport == "Yes":
                                        # Check if instance is in ASG
                                        for j in asgmembers:
                                            if i.instance_id == j['InstanceId']:
                                                print ("|--> is member of ASG ", j['AutoScalingGroupName'], "--> added to INSERVICE list")
                                                InServiceList[j['AutoScalingGroupName']].append(i.instance_id)
                                                
                                # Instance Id already in startList
                                
                            # Append to stop list
                            if action == "STOP" and state == "running":
                                if i.instance_id not in stopList:
                                    stopList.append(i.instance_id)
                                    print (i.instance_id, "with tag", t['Value'], "added to STOP list")
                                    
                                    if ASGSupport == "Yes":
                                        # Check if instance is in ASG
                                        for j in asgmembers:
                                            if i.instance_id == j['InstanceId']:
                                                print ("|--> is member of ASG ", j['AutoScalingGroupName'], "--> added to STANDBY list")
                                                StandbyList[j['AutoScalingGroupName']].append(i.instance_id)
                                                
                                # Instance Id already in stopList
                                
            print ("*** Execute EC2 actions")
            
            if startList or stopList:
                if startList:
                    print ("Starting", len(startList), "instances:", startList)
                    ec2.instances.filter(InstanceIds=startList).start()
                    if createMetrics == "Yes":
                        for i in startList:
                            putCloudWatchMetric(region_name, i, 1)
                else:
                    print ("No Instances to start in region",  region_name)
                    
                if ASGSupport == "Yes":
                    if InServiceList:
                        # Loop through ASGs
                        for asg, instances in InServiceList.items():
                            try:
                                print ("Putting", len(instances), "instances in ASG", asg, "in service:", instances)
                                
                                # Make sure the instances are started before proceeding
                                for i in instances:
                                    print ("|--> Checking if instance", i, "is in running state")
                                    instance_state = ec2.Instance(i).state['Name']
                                    
                                    while instance_state != "running":
                                        instance_state = ec2.Instance(i).state['Name']
                                        print ("|----> Waiting for instance", i, "to enter running state")
                                        time.sleep(3)
                                        
                                # Set instances to InService
                                aws_scaling_client.exit_standby(InstanceIds=instances, AutoScalingGroupName=asg)
                                
                            except Exception as e:
                                print ("|-->", e)
                                
                    else:
                        print ("No Instances to put in service in region",  region_name)
                        
                    if StandbyList:
                        # Loop through ASGs
                        for asg, instances in StandbyList.items():
                            try:
                                print ("Putting", len(instances), "instances in ASG", asg, "to standby:", instances)
                                
                                # Check maximum amount of instances that can be set to Standby depending on Min-Value of ASG
                                asg_result = aws_scaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg])
                                desired = asg_result['AutoScalingGroups'][0]['DesiredCapacity']
                                min = asg_result['AutoScalingGroups'][0]['MinSize']
                                maxStandby = desired - min
                                
                                # If more instances than allowed are in StandbyList, remove them from StandbyList and stopList
                                if maxStandby <= 0:
                                    print ("|--> ASG", asg, "has values of Desired", desired, "and Min", min, "--> Can't set any instances to standby")
                                    print ("|----> Removing instances from STANDBY and STOP lists:", instances)
                                    stopList = [e for e in stopList if e not in instances]
                                    print ("Putting no instances in ASG", asg, "to standby")
                                    continue
                                
                                elif len(instances) > maxStandby:
                                    print ("|--> ASG", asg, "has values of Desired", desired, "and Min", min, "--> Can set only", maxStandby, " (Desired - Min) instances to standby")
                                    instancesToRemove = instances[maxStandby:]
                                    print ("|----> Removing excess instances from STANDBY and STOP lists:", instancesToRemove)
                                    instances = instances[:maxStandby]
                                    stopList = [e for e in stopList if e not in instancesToRemove]
                                    print ("Putting only", len(instances), "instances in ASG", asg, "to standby:", instances)
                                    
                                # Set instances to Standby
                                aws_scaling_client.enter_standby(InstanceIds=instances, AutoScalingGroupName=asg, ShouldDecrementDesiredCapacity=True)
                                
                                # Make sure the instances are in Standby before proceeding
                                for i in instances:
                                    print ("|--> Checking if instance", i, "is in standby state")
                                    instance_result = aws_scaling_client.describe_auto_scaling_instances(InstanceIds=[i])
                                    instance_state = instance_result['AutoScalingInstances'][0]['LifecycleState']
                                    
                                    while instance_state != "Standby":
                                        instance_result = aws_scaling_client.describe_auto_scaling_instances(InstanceIds=[i])
                                        instance_state = instance_result['AutoScalingInstances'][0]['LifecycleState']
                                        print ("|----> Waiting for instance", i, "to enter standby state")
                                        time.sleep(3)
                                        
                            except Exception as e:
                                print ("|-->", e)
                                # Remove failed instances from stopList
                                stopList = [e for e in stopList if e not in instances]
                                print ("|----> Removing instances from STOP list:", instances)
                                
                    else:
                        print ("No Instances to put to standby in region",  region_name)
                        
                if stopList:
                    print ("Stopping", len(stopList) ,"instances:", stopList)
                    ec2.instances.filter(InstanceIds=stopList).stop()
                    if createMetrics == "Yes":
                        for i in stopList:
                            putCloudWatchMetric(region_name, i, 0)
                    
                else:
                    print ("No Instances to stop in region", region_name)
                    
            else:
                print ("(Nothing to do)")
                
        except Exception as e:
            print ("Exception:", e)
            continue
        
        if RDSSupport == "Yes":
            # Declare Lists
            rdsStartList = []
            rdsStopList = []
            
            try:
                rds = boto3.client('rds', region_name =  region_name)
                rds_instances = rds.describe_db_instances()
                
                print ("*** Populate RDS lists")
                
                for rds_instance in rds_instances['DBInstances']:
                    
                    if len(rds_instance['ReadReplicaDBInstanceIdentifiers']):
                        print ("No action against RDS instance", rds_instance['DBInstanceIdentifier'], "(has read replica)")
                        continue
                    
                    if "ReadReplicaSourceDBInstanceIdentifier" in rds_instance.keys():
                        print ("No action against RDS instance", rds_instance['DBInstanceIdentifier'], "(is replicating)")
                        continue
                    
                    if rds_instance['MultiAZ']:
                        print ("No action against RDS instance", rds_instance['DBInstanceIdentifier'], "(is in multiple AZs)")
                        continue
                    
                    if rds_instance['DBInstanceStatus'] not in ["available","stopped"]:
                        print ("No action against RDS instance", rds_instance['DBInstanceIdentifier'], "(is in an unsupported state)")
                        continue
                    
                    # Query RDS instance tags 
                    response = rds.list_tags_for_resource( ResourceName = rds_instance['DBInstanceArn'])
                    tags = response['TagList']
                    
                    for t in tags:
                        # Search tag
                        if t['Key'][:customRDSTagLen] == customRDSTagName:
                            
                            state = rds_instance['DBInstanceStatus']
                            
                            # Post current state of the instance
                            if createMetrics == "Yes":
                                if state == "available":
                                    putCloudWatchMetric(region_name, rds_instance['DBInstanceIdentifier'], 1)
                                if state == "stopped":
                                    putCloudWatchMetric(region_name, rds_instance['DBInstanceIdentifier'], 0)
                            
                            action = scheduler_action(tagValue = t['Value'])
                            state = rds_instance['DBInstanceStatus']
                            
                            # Append to start list
                            if action == "START" and state == "stopped":
                                if rds_instance['DBInstanceIdentifier'] not in rdsStartList:
                                    rdsStartList.append(rds_instance['DBInstanceIdentifier'])
                                    print (rds_instance['DBInstanceIdentifier'], "with tag", t['Value'], "added to RDS START list")
                                # Instance Id already in rdsStartList
                                
                            # Append to stop list
                            if action == "STOP" and state == "available":
                                if rds_instance['DBInstanceIdentifier'] not in rdsStopList:
                                    rdsStopList.append(rds_instance['DBInstanceIdentifier'])
                                    print (rds_instance['DBInstanceIdentifier'], "with tag", t['Value'], "added to RDS STOP list")
                                # Instance Id already in rdsStopList
                                
                print ("*** Execute RDS actions")
                
                if rdsStartList or rdsStopList:
                    # Execute Start and Stop Commands
                    if rdsStartList:
                        print ("Starting", len(rdsStartList), "RDS instances:", rdsStartList)
                        for DBInstanceIdentifier in rdsStartList:
                            rds.start_db_instance(DBInstanceIdentifier = DBInstanceIdentifier)
                            if createMetrics == "Yes":
                                putCloudWatchMetric(region_name, DBInstanceIdentifier, 1)
                            
                    else:
                        print ("No RDS Instances to Start in region",  region_name)
                        
                    if rdsStopList:
                        print ("Stopping", len(rdsStopList) ,"RDS instances:", rdsStopList)
                        for DBInstanceIdentifier in rdsStopList:
                            rds.stop_db_instance(DBInstanceIdentifier = DBInstanceIdentifier)
                            if createMetrics == "Yes":
                                putCloudWatchMetric(region_name, DBInstanceIdentifier, 0)
                            
                    else:
                        print ("No RDS Instances to Stop in region", region_name)
                        
                else:
                    print ("(Nothing to do)")
                    
            except Exception as e:
                print ("Exception:", e)
                continue
            
    print ("* EC2 and RDS Scheduler finished")
    
# Local version
if  __name__ =='__main__':
    event = {
        "DefaultStartTime": "0800",
        "DefaultStopTime": "1800",
        "DefaultDaysActive": "all",
        "Regions": "eu-west-1",
        "DefaultTimeZone": "Europe/Zurich",
        "RDSSupport": "Yes",
        "ASGSupport": "Yes",
        "CustomTagName": "scheduler:ec2-startstop",
        "CustomRDSTagName": "scheduler:rds-startstop",
        "CloudWatchMetrics": "Enabled",
        "Schedule": "1hour"
    }
    
    context = None
    
    lambda_handler(event = event, context = context)
    
#EOF
