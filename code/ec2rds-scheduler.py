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

# Import re to analyse month day
import re

# Import pytz to support local timezone
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

    if startTime >= str(nowMax) and startTime <= str(now) and isActiveDay == True and isValidTimeZone == True:
        Action = "START"

    if stopTime >= str(nowMax) and stopTime <= str(now) and isActiveDay == True and isValidTimeZone == True:
        Action = "STOP"

    return Action

def lambda_handler(event, context):
    print ("* EC2 and RDS Scheduler started")
    
    global defaultStartTime
    global defaultStopTime
    global defaultTimeZone
    global defaultDaysActive
    global Schedule
    global now
    global nowMax
    global tz
    
     # Set global default value from CloudWatch Rule Input event
    defaultStartTime = event['DefaultStartTime'].replace("'","")
    defaultStopTime = event['DefaultStopTime'].replace("'","")
    defaultTimeZone = event['DefaultTimeZone']
    defaultDaysActive = event['DefaultDaysActive']
    
    # Default Timzone
    tz = pytz.timezone(defaultTimeZone)
    
    # Set time/day variables
    now = datetime.datetime.now(tz).strftime("%H%M")

     # Get schedule to know what timerange to cover
    scheduleDict =	{
      "1minute": 0,
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

    nowDay = datetime.datetime.now(tz).strftime("%a").lower()
    nowDate = int(datetime.datetime.now(tz).strftime("%d"))

    # Customized tag name
    customTagName = event['CustomTagName']
    customTagLen = len(customTagName)
    createMetrics = event['CloudWatchMetrics'].lower()
    ASGSupport = event['ASGSupport']

    # Customized RDS tag name
    RDSSupport = event['RDSSupport']
    customRDSTagName = event['CustomRDSTagName']
    customRDSTagLen = len(customRDSTagName)

    # Create connection to the EC2 using Boto3 client interface
    ec2 = boto3.client('ec2')

    if event['Regions'] == 'all':
        AwsRegionNames = []
        for r in ec2.describe_regions()['Regions']:
            AwsRegionNames.append(r['RegionName'])
    else:
        AwsRegionNames = event['Regions'].split()

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
            # Declare Lists
            startList = []
            stopList = []
            if ASGSupport == "Yes":
                InServiceList = []
                StandbyList = defaultdict(list)
            
            # Create connection to the EC2 using Boto3 resources interface
            ec2 = boto3.resource('ec2', region_name = region_name)

            # List all instances
            instances = ec2.instances.all()

            if ASGSupport == "Yes":
                # Create connection to Autoscaling using Boto3 client interface
                aws_scaling_client = boto3.client('autoscaling', region_name = region_name)
    
                next_token = ''
                while next_token is not None:
                    if next_token is not '':
                        describe_result = aws_scaling_client.describe_auto_scaling_instances(NextToken=next_token)
                    else:
                        describe_result = aws_scaling_client.describe_auto_scaling_instances()
                    next_token = describe_result.get('NextToken')
    
                # List all ASG members
                asgmembers = describe_result.get('AutoScalingInstances')

            print ("*** Populate EC2 lists")
            for i in instances:
                if i.tags != None:
                    for t in i.tags:
                        if t['Key'][:customTagLen] == customTagName:

                            state = i.state['Name']

                            # Post current state of the instances
                            if createMetrics == 'enabled':
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
                                    print (i.instance_id, " added to START list")
                                    if ASGSupport == "Yes":
                                        # Check if instance is in ASG
                                        for j in asgmembers:
                                            if i.instance_id == j['InstanceId']:
                                                print ("|--> is member of ASG ", j['AutoScalingGroupName'], "--> adding the instance to InServiceList")
                                                InServiceList.append([i.instance_id,j['AutoScalingGroupName']])
                                    if createMetrics == 'enabled':
                                        putCloudWatchMetric(region_name, i.instance_id, 1)
                                # Instance Id already in startList

                            # Append to stop list
                            if action == "STOP" and state == "running":
                                if i.instance_id not in stopList:
                                    stopList.append(i.instance_id)
                                    print (i.instance_id, " added to STOP list")
                                    if ASGSupport == "Yes":
                                        # Check if instance is in ASG
                                        for j in asgmembers:
                                            if i.instance_id == j['InstanceId']:
                                                print ("|--> is member of ASG ", j['AutoScalingGroupName'], "--> adding the instance to StandbyList")
                                                StandbyList[j['AutoScalingGroupName']].append(i.instance_id)
                                    if createMetrics == 'enabled':
                                        putCloudWatchMetric(region_name, i.instance_id, 0)
                                # Instance Id already in stopList

            print ("*** Execute EC2 actions")
            if startList or stopList:
                # Execute Start and Stop Commands
                if startList:
                    print ("Starting", len(startList), "instances", startList)
                    ec2.instances.filter(InstanceIds=startList).start()
                else:
                    print ("No Instances to Start in region ",  region_name)
    
                if ASGSupport == "Yes":
                    if InServiceList:
                        for i in InServiceList:
                            # Make sure the instance is started before proceeding
                            instance_state = ec2.Instance(i[0]).state['Name']
                            while instance_state != "running":
                                instance_state = ec2.Instance(i[0]).state['Name']
                                print ("|--> Waiting for instance", i[0], "to enter running state...")
                                time.sleep(2)
                            aws_scaling_client.exit_standby(InstanceIds=[i[0]], AutoScalingGroupName=i[1])
                        print ("Putting", len(InServiceList), "instances InService", InServiceList)
                    else:
                        print ("No Instances to put InService in region ",  region_name)
        
                    if StandbyList:
                        for asg, instances in StandbyList.items():
                            try:
                                print ("Putting the following instances in ASG", asg, " to Standby:", instances)
                                aws_scaling_client.enter_standby(InstanceIds=instances, AutoScalingGroupName=asg, ShouldDecrementDesiredCapacity=True)
                                # Make sure the instance is in standby before proceeding
                                instance_state = ""
                                while instance_state != "Standby":
                                    instance_result = aws_scaling_client.describe_auto_scaling_instances(InstanceIds=instances)
                                    instance_state = instance_result['AutoScalingInstances'][0]['LifecycleState']
                                    print ("|--> Waiting for instance", instances[0], "to enter standby state...")
                                    time.sleep(2)
                            except Exception as e:
                                print ("|-->", e)
                                stopList = [e for e in stopList if e not in instances]
                                print ("|---->", instances, " removed from STOP list")
                    else:
                        print ("No Instances to put to Standby in region ",  region_name)
    
                if stopList:
                    print ("Stopping", len(stopList) ,"instances", stopList)
                    ec2.instances.filter(InstanceIds=stopList).stop()
                else:
                    print ("No Instances to Stop in region ", region_name)
            else:
                print ("Nothing to do...")
        except Exception as e:
            print ("Exception: "+str(e))
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
                        if t['Key'][:customRDSTagLen] == customRDSTagName:

                            action = scheduler_action(tagValue = t['Value'])
                            state = rds_instance['DBInstanceStatus']

                            # Append to start list
                            if action == "START" and state == "stopped":
                                if rds_instance['DBInstanceIdentifier'] not in rdsStartList:
                                    rdsStartList.append(rds_instance['DBInstanceIdentifier'])
                                    print (rds_instance['DBInstanceIdentifier'], " added to RDS START list")
                                # Instance Id already in rdsStartList

                            # Append to stop list
                            if action == "STOP" and state == "available":
                                if rds_instance['DBInstanceIdentifier'] not in rdsStopList:
                                    rdsStopList.append(rds_instance['DBInstanceIdentifier'])
                                    print (rds_instance['DBInstanceIdentifier'], " added to RDS STOP list")
                                # Instance Id already in rdsStopList

                print ("*** Execute RDS actions")
                if rdsStartList or rdsStopList:
                    # Execute Start and Stop Commands
                    if rdsStartList:
                        print ("Starting", len(rdsStartList), "RDS instances", rdsStartList)
                        for DBInstanceIdentifier in rdsStartList:
                            rds.start_db_instance(DBInstanceIdentifier = DBInstanceIdentifier)
                    else:
                        print ("No RDS Instances to Start in region ",  region_name)
    
                    if rdsStopList:
                        print ("Stopping", len(rdsStopList) ,"RDS instances", rdsStopList)
                        for DBInstanceIdentifier in rdsStopList:
                            rds.stop_db_instance(DBInstanceIdentifier = DBInstanceIdentifier)
                    else:
                        print ("No RDS Instances to Stop in region ", region_name)
                else:
                    print ("Nothing to do...")
            except Exception as e:
                print ("Exception: "+str(e))
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
