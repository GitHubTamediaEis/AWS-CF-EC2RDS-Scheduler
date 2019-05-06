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
import time
import datetime
import re
import pytz
from collections import defaultdict

# Function to push CloudWatch metrics
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

# Function to interpret the tag of an instance and return the action to do
def scheduler_action(tagValue):
    
    # Weekdays Interpreter
    weekdays = ['mon', 'tue', 'wed', 'thu', 'fri']
    
    # Monthdays Interpreter (1..31)
    monthdays = re.compile(r'^(0?[1-9]|[12]\d|3[01])$')
    
    # nth weekdays Interpreter
    nthweekdays=re.compile('\w{3}/\d{1}')
    
    # Set default values
    Action = 'None'
    isValidTimeZone = True
    isActiveDay = False
    
    # Get tag values
    ptag = tagValue.replace(';',':').split(':')
    
    # Get default time values
    startTime = defaultStartTime
    stopTime = defaultStopTime
    timeZone = defaultTimeZone
    daysActive = defaultDaysActive

    # Check if tag is empty or none
    if (ptag[0] == '' or ptag[0] == 'none') and len(ptag) == 1:
        return 'None'

    # Get startTime
    if len(ptag) >= 1:
        # Check for default values
        if ptag[0].lower() not in ('default', 'true'):
            startTime = ptag[0]
            # Clear default stopTime if stopTime it's not defined in tag
            if len(ptag) == 1:
                stopTime = ''
            
    # Support 24x7
    if startTime  == '24x7':
        return 'START'
        
    # Get stopTime
    if len(ptag) >= 2:
        stopTime = ptag[1]
        
    # Default Timzone
    tz = pytz.timezone(defaultTimeZone)
    
    # Get timezone
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
                    print ('Invalid time zone :', timeZone)
                    isValidTimeZone = False
            # utc timezone
            else:
                tz = pytz.timezone('utc')
                
    # Get datetime
    datetimevalue = datetime.datetime.fromtimestamp(timestamp, tz)
    
    # Set time/day variables
    now = datetimevalue.strftime('%H%M')
    
    # Set nowMin to now minus schedule plus 1min
    nowMin = datetimevalue + datetime.timedelta(minutes=-schedule+1)
    nowMin = nowMin.strftime('%H%M')
        
    # Set day and date
    nowDay = datetimevalue.strftime('%a').lower()
    nowDate = int(datetimevalue.strftime('%d'))
    
    # Handle midnight (script must look back to the day before, so set current day to yesterday if needed)
    if str(now) == '0000':
        # If startTime isn't 00:00 but matches the range, go one day back
        if startTime != '0000' and startTime >= str(nowMin):
            minusOneDay = datetimevalue + datetime.timedelta(days=-1)
            nowDay = minusOneDay.strftime('%a').lower()
            nowDate = int(minusOneDay.strftime('%d'))
            now = '2359'
            # If startTime and stopTime fall in the same execution, do noting
            if stopTime == '0000':
                print ('**** Tag with value', tagValue, 'is invalid (start- and stopTime fall in the same execution interval)')
                return 'None'
        # If stopTime isn't 00:00 but matches the range, go one day back
        if stopTime != '0000' and stopTime >= str(nowMin):
            minusOneDay = datetimevalue + datetime.timedelta(days=-1)
            nowDay = minusOneDay.strftime('%a').lower()
            nowDate = int(minusOneDay.strftime('%d'))
            now = '2359'
            # If startTime and stopTime fall in the same execution, do noting
            if startTime == '0000':
                print ('**** Tag with value', tagValue, 'is invalid (start- and stopTime fall in the same execution interval)')
                return 'None'
        # If start- or stopTime is 00:00, set nowMin to 00:00
        if startTime == '0000' or stopTime == '0000':
            nowMin = '0000'
    
    # Get active days
    if len(ptag) >= 4:
        daysActive = ptag[3].lower()
    
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
           
    # All days support
    elif daysActive == 'all':
        isActiveDay = True
        
    # Weekdays support
    elif daysActive == 'weekdays':
        if (nowDay in weekdays):
            isActiveDay = True
            
    # Specific days support
    else:
        for d in daysActive.split(','):
            # mon,tue,wed,thu,fri,sat,sun ?
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
                (weekday,nthweek) = d.split('/')
                if (weekday.lower() == nowDay) and ( nowDate >= (int(nthweek) * 7 - 6)) and (nowDate <= (int(nthweek) * 7)):
                   isActiveDay = True
                   
    # Should instance be started?
    if startTime >= str(nowMin) and startTime <= str(now) and isActiveDay == True and isValidTimeZone == True:
        Action = 'START'
        
    # Should instance be stopped?    
    if stopTime >= str(nowMin) and stopTime <= str(now) and isActiveDay == True and isValidTimeZone == True:
        # If both START and STOP match, do noting
        if Action == 'START':
            print ('**** Tag with value', tagValue, 'is invalid (start- and stopTime fall in the same execution interval)')
            return 'None'
        Action = 'STOP'
        
    return Action

# Function gets called by CloudWatch event based on configured schedule
def lambda_handler(event, context):
    
    print ('* EC2 and RDS Scheduler started')
    
    # Define global variables
    global defaultStartTime
    global defaultStopTime
    global defaultTimeZone
    global defaultDaysActive
    global schedule
    global timestamp
    
    ## Set global default values from CloudWatch Rule Input event
    # Customized time values
    defaultStartTime = event['DefaultStartTime'].replace("'",'')
    defaultStopTime = event['DefaultStopTime'].replace("'",'')
    defaultTimeZone = event['DefaultTimeZone']
    defaultDaysActive = event['DefaultDaysActive']
    print('* Default values are StartTime:',defaultStartTime,'StopTime:',defaultStopTime,'TimeZone:',defaultTimeZone,'DaysActive:',defaultDaysActive)
    
    # Customized tag name
    customTagName = event['CustomTagName']
    customTagLen = len(customTagName)
    createMetrics = event['CloudWatchMetrics']
    ASGSupport = event['ASGSupport']
    
    # Customized RDS tag name
    RDSSupport = event['RDSSupport']
    customRDSTagName = event['CustomRDSTagName']
    customRDSTagLen = len(customRDSTagName)
    
    # Get current timestamp
    timestamp = time.time()
    
     # Get schedule to know what timerange to cover
    scheduleDict =	{
      '5minutes': 5,
      '15minutes': 15,
      '30minutes': 30,
      '1hour': 60
    }
    schedule = scheduleDict[event['Schedule']]
    
    # Create connection to the EC2 using Boto3 client interface
    ec2 = boto3.client('ec2')
    
    # Set regions
    if event['Regions'] == 'all':
        AwsRegionNames = []
        for r in ec2.describe_regions()['Regions']:
            AwsRegionNames.append(r['RegionName'])
    else:
        AwsRegionNames = event['Regions'].split(',')
        
    print ('* Operate in regions:', ', '.join(AwsRegionNames))
    
    # RDS support?
    if RDSSupport == 'Yes':
        print ('* RDS support is enabled')
    else:
        print ('* RDS support is disabled')
        
    # ASG support?
    if ASGSupport == 'Yes':
        print ('* ASG support is enabled')
    else:
        print ('* ASG support is disabled')
        
    # Loop through regions
    for region_name in AwsRegionNames:
        try:
            
            print ('**', region_name)
            
            # Declare lists and dicts
            startList = []
            stopList = []
            
            if ASGSupport == 'Yes':
                InServiceList = defaultdict(list)
                StandbyList = defaultdict(list)
                
            # Create connection to the EC2 using Boto3 resources interface
            ec2 = boto3.resource('ec2', region_name = region_name)
            
            # List all instances
            instances = ec2.instances.all()
            
            if ASGSupport == 'Yes':
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
                
            # Create list of instances that need a metric update
            if createMetrics == 'Yes':
                metricUpList = []
                metricDownList = []
                
            print ('*** Populate EC2 lists')
            
            for i in instances:
                # Search tag
                if i.tags != None:
                    for t in i.tags:
                        if t['Key'][:customTagLen] == customTagName:
                            
                            # Get instance state
                            state = i.state['Name']
                            
                            # Add instances to correct metricList
                            if createMetrics == 'Yes':
                                if state == 'running':
                                    metricUpList.append(i.instance_id)
                                if state == 'stopped':
                                    metricDownList.append(i.instance_id)
                                    
                            # Get action for instance
                            action = scheduler_action(tagValue = t['Value'])
                            
                            # Append to start list
                            if action == 'START' and state == 'stopped':
                                if i.instance_id not in startList:
                                    startList.append(i.instance_id)
                                    print ('****', i.instance_id, 'with tag', t['Value'], 'added to START list')
                                    
                                    if ASGSupport == 'Yes':
                                        # Check if instance is in ASG
                                        for j in asgmembers:
                                            if i.instance_id == j['InstanceId']:
                                                print ('**** |--> is member of ASG ', j['AutoScalingGroupName'], '--> added to INSERVICE list')
                                                InServiceList[j['AutoScalingGroupName']].append(i.instance_id)
                                                
                                # Instance Id already in startList
                                
                            # Append to stop list
                            if action == 'STOP' and state == 'running':
                                if i.instance_id not in stopList:
                                    stopList.append(i.instance_id)
                                    print ('****', i.instance_id, 'with tag', t['Value'], 'added to STOP list')
                                    
                                    if ASGSupport == 'Yes':
                                        # Check if instance is in ASG
                                        for j in asgmembers:
                                            if i.instance_id == j['InstanceId']:
                                                print ('**** |--> is member of ASG ', j['AutoScalingGroupName'], '--> added to STANDBY list')
                                                StandbyList[j['AutoScalingGroupName']].append(i.instance_id)
                                                
                                # Instance Id already in stopList
                                
            print ('*** Execute EC2 actions')
            
            if startList or stopList:
                if startList:
                    print ('**** Starting', len(startList), 'instances:', ', '.join(startList))
                    ec2.instances.filter(InstanceIds=startList).start()
                    if createMetrics == 'Yes':
                        # Remove instances in startList from metricDownList
                        metricDownList = [e for e in metricDownList if e not in startList]
                        # Post metrics for instances that were stopped
                        for i in startList:
                            putCloudWatchMetric(region_name, i, 1)
                else:
                    print ('**** No Instances to start in region',  region_name)
                    
                if ASGSupport == 'Yes':
                    if InServiceList:
                        # Loop through ASGs
                        for asg, instances in InServiceList.items():
                            try:
                                print ('**** Putting', len(instances), 'instances in ASG', asg, 'in service:', ', '.join(instances))
                                
                                # Make sure the instances are started before proceeding
                                for i in instances:
                                    print ('**** |--> Checking if instance', i, 'is in running state')
                                    instance_state = ec2.Instance(i).state['Name']
                                    
                                    while instance_state != 'running':
                                        instance_state = ec2.Instance(i).state['Name']
                                        print ('**** |----> Waiting for instance', i, 'to enter running state')
                                        time.sleep(3)
                                        
                                # Set instances to InService
                                aws_scaling_client.exit_standby(InstanceIds=instances, AutoScalingGroupName=asg)
                                
                            except Exception as e:
                                print ('**** |-->', e)
                                
                    else:
                        print ('**** No Instances to put in service in region',  region_name)
                        
                    if StandbyList:
                        # Loop through ASGs
                        for asg, instances in StandbyList.items():
                            try:
                                print ('**** Putting', len(instances), 'instances in ASG', asg, 'to standby:', ', '.join(instances))
                                
                                # Check maximum amount of instances that can be set to Standby depending on Min-Value of ASG
                                asg_result = aws_scaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg])
                                desired = asg_result['AutoScalingGroups'][0]['DesiredCapacity']
                                min = asg_result['AutoScalingGroups'][0]['MinSize']
                                maxStandby = desired - min
                                
                                # If more instances than allowed are in StandbyList, remove them from StandbyList and stopList
                                if maxStandby <= 0:
                                    print ('**** |--> ASG', asg, 'has values of Desired', desired, 'and Min', min, "--> Can't set any instances to standby")
                                    print ('**** |----> Removing instances from STANDBY and STOP lists:', ', '.join(instances))
                                    stopList = [e for e in stopList if e not in instances]
                                    print ('**** Putting no instances in ASG', asg, 'to standby')
                                    continue
                                
                                elif len(instances) > maxStandby:
                                    print ('**** |--> ASG', asg, 'has values of Desired', desired, 'and Min', min, '--> Can set only', maxStandby, ' (Desired - Min) instances to standby')
                                    instancesToRemove = instances[maxStandby:]
                                    print ('**** |----> Removing excess instances from STANDBY and STOP lists:', ', '.join(instancesToRemove))
                                    instances = instances[:maxStandby]
                                    stopList = [e for e in stopList if e not in instancesToRemove]
                                    print ('**** Putting only', len(instances), 'instances in ASG', asg, 'to standby:', ', '.join(instances))
                                    
                                # Set instances to Standby
                                aws_scaling_client.enter_standby(InstanceIds=instances, AutoScalingGroupName=asg, ShouldDecrementDesiredCapacity=True)
                                
                                # Make sure the instances are in Standby before proceeding
                                for i in instances:
                                    print ('**** |--> Checking if instance', i, 'is in standby state')
                                    instance_result = aws_scaling_client.describe_auto_scaling_instances(InstanceIds=[i])
                                    instance_state = instance_result['AutoScalingInstances'][0]['LifecycleState']
                                    
                                    while instance_state != 'Standby':
                                        instance_result = aws_scaling_client.describe_auto_scaling_instances(InstanceIds=[i])
                                        instance_state = instance_result['AutoScalingInstances'][0]['LifecycleState']
                                        print ('**** |----> Waiting for instance', i, 'to enter standby state')
                                        time.sleep(3)
                                        
                            except Exception as e:
                                print ('**** |-->', e)
                                # Remove failed instances from stopList
                                stopList = [e for e in stopList if e not in instances]
                                print ('**** |----> Removing instances from STOP list:', ', '.join(instances))
                                
                    else:
                        print ('**** No Instances to put to standby in region', region_name)
                        
                if stopList:
                    print ('**** Stopping', len(stopList) ,'instances:', ', '.join(stopList))
                    ec2.instances.filter(InstanceIds=stopList).stop()
                    if createMetrics == 'Yes':
                        # Remove instances in stopList from metricUpList
                        metricUpList = [e for e in metricUpList if e not in stopList]
                        # Post metrics for instances that were stopped
                        for i in stopList:
                            putCloudWatchMetric(region_name, i, 0)
                    
                else:
                    print ('**** No Instances to stop in region', region_name)
                    
            else:
                print ('**** Nothing to do')
            
            # Post metrics for instances that were not stopped or started
            if createMetrics == 'Yes':
                for i in metricUpList:
                    putCloudWatchMetric(region_name, i, 1)
                for i in metricDownList:
                    putCloudWatchMetric(region_name, i, 0)
                
        except Exception as e:
            print ('** Exception:', e)
            continue
        
        if RDSSupport == 'Yes':
            # Declare Lists
            rdsStartList = []
            rdsStopList = []
            
        # Create list of instances that need a metric update
        if createMetrics == 'Yes':
            metricUpList = []
            metricDownList = []
            
            try:
                rds = boto3.client('rds', region_name =  region_name)
                rds_instances = rds.describe_db_instances()
                
                print ('*** Populate RDS lists')
                
                for rds_instance in rds_instances['DBInstances']:
                    
                    # Query RDS instance tags 
                    response = rds.list_tags_for_resource( ResourceName = rds_instance['DBInstanceArn'])
                    tags = response['TagList']
                    
                    for t in tags:
                        # Search tag
                        if t['Key'][:customRDSTagLen] == customRDSTagName:
                            
                            # Get instance state
                            state = rds_instance['DBInstanceStatus']
                            
                            # Add instances to correct metricList
                            if createMetrics == 'Yes':
                                if state in ['available','starting']:
                                    metricUpList.append(rds_instance['DBInstanceIdentifier'])
                                if state in ['stopped','stopping']:
                                    metricDownList.append(rds_instance['DBInstanceIdentifier'])
                            
                            # Get action for instance
                            action = scheduler_action(tagValue = t['Value'])
                            
                            # Check for unsupported instances
                            if action != "None":
                                if len(rds_instance['ReadReplicaDBInstanceIdentifiers']):
                                    print ('**** No action against RDS instance', rds_instance['DBInstanceIdentifier'], '(has read replica)')
                                    continue
                                
                                if 'ReadReplicaSourceDBInstanceIdentifier' in rds_instance.keys():
                                    print ('**** No action against RDS instance', rds_instance['DBInstanceIdentifier'], '(is replicating)')
                                    continue
                                
                                if rds_instance['MultiAZ']:
                                    print ('**** No action against RDS instance', rds_instance['DBInstanceIdentifier'], '(is in multiple AZs)')
                                    continue
                                
                                if state not in ['available','stopped']:
                                    print ('**** No action against RDS instance', rds_instance['DBInstanceIdentifier'], '(is in an unsupported state:',state,')')
                                    continue
                            
                            # Append to start list
                            if action == 'START' and state == 'stopped':
                                if rds_instance['DBInstanceIdentifier'] not in rdsStartList:
                                    rdsStartList.append(rds_instance['DBInstanceIdentifier'])
                                    print ('****', rds_instance['DBInstanceIdentifier'], 'with tag', t['Value'], 'added to RDS START list')
                                # Instance Id already in rdsStartList
                                
                            # Append to stop list
                            if action == 'STOP' and state == 'available':
                                if rds_instance['DBInstanceIdentifier'] not in rdsStopList:
                                    rdsStopList.append(rds_instance['DBInstanceIdentifier'])
                                    print ('****', rds_instance['DBInstanceIdentifier'], 'with tag', t['Value'], 'added to RDS STOP list')
                                # Instance Id already in rdsStopList
                                
                print ('*** Execute RDS actions')
                
                if rdsStartList or rdsStopList:
                    # Execute Start and Stop Commands
                    if rdsStartList:
                        print ('**** Starting', len(rdsStartList), 'RDS instances:', ', '.join(rdsStartList))
                        for DBInstanceIdentifier in rdsStartList:
                            rds.start_db_instance(DBInstanceIdentifier = DBInstanceIdentifier)
                            if createMetrics == 'Yes':
                                # Remove instances in rdsStartList from metricDownList
                                metricDownList = [e for e in metricDownList if e not in rdsStartList]
                                # Post metrics for instances that were started
                                putCloudWatchMetric(region_name, DBInstanceIdentifier, 1)
                            
                    else:
                        print ('**** No RDS Instances to Start in region',  region_name)
                        
                    if rdsStopList:
                        print ('**** Stopping', len(rdsStopList) ,'RDS instances:', ', '.join(rdsStopList))
                        for DBInstanceIdentifier in rdsStopList:
                            rds.stop_db_instance(DBInstanceIdentifier = DBInstanceIdentifier)
                            if createMetrics == 'Yes':
                                # Remove instances in rdsStopList from metricUpList
                                metricUpList = [e for e in metricUpList if e not in rdsStopList]
                                # Post metrics for instances that were stopped
                                putCloudWatchMetric(region_name, DBInstanceIdentifier, 0)
                            
                    else:
                        print ('**** No RDS Instances to Stop in region', region_name)
                        
                else:
                    print ('**** Nothing to do')
                    
                # Post metrics for instances that were not stopped or started
                if createMetrics == 'Yes':
                    for i in metricUpList:
                        putCloudWatchMetric(region_name, i, 1)
                    for i in metricDownList:
                        putCloudWatchMetric(region_name, i, 0)
                    
            except Exception as e:
                print ('** Exception:', e)
                continue
            
    print ('* EC2 and RDS Scheduler finished')
    
#EOF
