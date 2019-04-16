# AWS-CF-EC2RDS-Scheduler

This is a solution to enable the scheduling of EC2 and RDS instances, so that they can be started and stopped automatically. It is deployed via [CodePipeline](https://docs.aws.amazon.com/codepipeline/index.html) and composed of the following files:

# code/ec2rds-scheduler.py

This file contains the lambda function code written in Python 3.7.

# EC2RDS-scheduler.yaml

This file is a CloudFormation template that enables the configuration and usage of the solution. It also creates a lambda function.

# buildspec.yaml
This file contains the [build specification reference](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html) for CodeBuild.

# Instructions

The solution is available in the [ServiceCatalog](https://docs.aws.amazon.com/servicecatalog/latest/userguide/end-user-console.html) of your account and can be easily deployed from there.

Upon deployment you have to specify custom parameters which are explained hereafter.

# Custom parameters

| Parameter | Default | Possible values | Notes |
| ------ | ------ | ------ | ------ |
|Schedule | 1hour | 5minutes, 15minutes, 30minutes, 1hour | Interval to execute the scheduler (See section *Schedule considerations*) |
|Regions | eu-west-1 | all, comma-separated list of regions | AWS regions to operate in |
|CustomTagName | scheduler:ec2-startstop | String | Tag name to use on EC2 instances |
|CustomRDSTagName | scheduler:rds-startstop | String | Tag name to use on RDS instances |
|DefaultStartTime | '0800' | Time in 24h format enclosed in '' | Default time to start tagged instances |
|DefaultStopTime | '1800' | Time in 24h format enclosed in '' | Default time to stop tagged instances |
|DefaultDaysActive| weekdays | all, weekdays, comma-separated list of days (mon, tue, wed, thu, fri, sat, sun), day number (1-31) or Nth day of month (wed/1, mon/3, ...) | Default days to start or stop tagged instances |
|DefaultTimeZone | Europe/Zurich | utc, Australia/Sydney, Etc/GMT+10, or any timezone supported by the pytz library | Timezone to use |
|ASGSupport | Yes | Yes, No | Support handling of Auto Scaling Groups (See section *Auto Scaling Groups considerations*) |
|RDSSupport | Yes | Yes, No | Support RDS instances (See section *RDS considerations*) |
|CloudWatchMetrics| Yes | Yes, No | Create CloudWatch metrics to track the state of instances (See section *CloudWatch metrics*) |

# How to use it

To start/stop EC2 instances on the default schedule, set the following tag on those instances:
Name: scheduler:ec2-startstop Value: default

To start/stop RDS instances on the default schedule, set the following tag on those instances:
Name: scheduler:rds-startstop Value: default

You can also set a custom tag value to EC2 or RDS instances in order to create a specific schedule for them.

The scheduler will read tag values, looking for four possible custom parameters in the following order, separated by colons: 
StartTime:StopTime:TimeZone:ActiveDays

The following table shows possible values for each field:

| Tag field | Possible values | Scheduled action/note |
| ------ | ------ | ------ | 
| StartTime | [empty] or none | No action |
|| default or true | Start and stop on the default schedule |
|| 24x7 | Start at any time |
|| 24x5 | Start at DefaultStartTime on Monday and stop it at DefaultStopTime on Friday |
|| HHMM | Start at the given time in 24h format |
| StopTime | [empty] or none | No action |
|| HHMM | Stop at the given time in 24h format |
| TimeZone | [empty] | Use default time zone |
|| utc | Use UTC time zone (case sensitive) |
|| Europe/Zurich | Use any [pytz library supported time zone](https://stackoverflow.com/questions/13866926/is-there-a-list-of-pytz-timezones) value (case sensitive) |
| ActiveDays | [empty] | Use default active days |
|| all | All days |
|| weekdays | From Monday to Friday |
|| 01,15 | 1st and 15th day of the month |
|| mon,fri | Every Monday and Friday |
|| sat,1,2 | Every Saturday and 1st and 2nd day of the month |
|| sat/2,fri/4 | Second Saturday and fourth Friday of the month |

# Example tag values

The following table gives examples of different tag values and the resulting scheduler actions

| Example Tag Value | EC2 Scheduler Action |
|------ | ------|
| [empty] or none | No action. |
| default or true | Start and stop on the default schedule (default timezone). |
| 24x7 | Always start. |
| 24x5 | Start at DefaultStartTime on Monday, and stop at DefaultStopTime on Friday (default timezone). |
| 24x5;;Europe/Zurich | Start at DefaultStartTime on Monday, and stop at DefaultStopTime on Friday (Europe/Zurich timezone). |
| 0800 | Start at 08:00 on DefaultDaysActive (default timezone). |
| ;1800 | Stop at 18:00 on DefaultDaysActive (default timezone). |
| ;1700;;weekdays | Stop at 17:00 on weekdays (default timezone). |
| 0800;1800 | Start at 08:00 and stop it at 18:00 on DefaultDaysActive (default timezone) |
| 0800;1800;Europe/Belgrade | Start at 08:00 and stop it at 18:00 on DefaultDaysActive (Europe/Belgrade timezone) |
| 0800;1800;utc;all | Start at 08:00 and stop at 18:00 on all days (UTC timezone). |
| 0000;1800;Etc/GMT+1;Mon/1 | Start at 00:00 and stop at 18:00 on the first Monday of the month (Etc/GMT+1 timezone). |
| 1000;1700;;weekdays | Start at 10:00 and stop at 17:00 Monday through Friday (default timezone). |
| 1030;1700;;mon,tue,fri | Start at 10:30 and stop at 17:00 on Monday, Tuesday and Friday only (default timezone). |
| 1030;1700;;mon,tue,fri,1,3 | Start at 10:30 and stop at 17:00 on Monday, Tuesday, Friday or on the 1st and 3rd day of the month (default timezone). |
| 1030;1700;;1 | Start at 10:30 and stop at 17:00 on the 1st day of the month (default timezone). |
| 1030;1700;;5,fri | Start at 10:30 and stop at 17:00 on the 5th day of the month and every Friday (default timezone). |
| 0815;1745;;wed,thu | Start at 08:15 and stop at 17:45 on Wednesday and Thursday (default timezone). |
| none;1800;;weekdays | Stop at 18:00 on Monday through Friday (default timezone). |
| 0800;none;;weekdays | Start at 08:00 on Monday through Friday (default timezone). |
| 1030;1700;;mon,tue,fri,1,3,sat/1 | Start at 10:30 and stop at 17:00 on every Monday, Tuesday, Friday as well as on the 1st and 3rd day of the month and the first Saturday of the month (default timezone). |

# Schedule considerations

The scheduler acts on time values that fall in the following time range: ((Time of execution) - (Schedule - 1)) to (Time of execution). Have a look at these examples:

- If the schedule is set to 1 hour, instances that have a start time of 13:01 - 14:00 will be started at 14:00.
- If the schedule is set to 5 minutes, instances that have a start time of 13:01 - 13:05 will be started at 13:05.

This means that all possible time values in tags are handled but the exact time of the start/stop operation depends on the schedule.

Best practice is to only use time values in tags that are a multiple of the configured schedule.

# Auto Scaling Groups considerations

Instances that are member of an Auto Scaling Group are set to Standby before they are stopped and put back InService after they are started. For this to work, the ASG's Min-Value must allow for the instances to be set to Standby. If that's not the case, the scheduler will only stop as much instances as the Min-Value of the ASG allows. For more information have a look at the following documentation: [Temporarily Removing Instances from Your Auto Scaling Group](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-enter-exit-standby.html)

Also be aware that instances that are automatically launched by an ASG inherit the tags from the ASG. So the best practice to set the scheduler-tag is to set them on the ASG instead of the instances. This way also newly launched instances have the scheduler-tag set.

Best practice for ASGs:
- Set the scheduler-tag on the ASG and activate "Tag new Instances".
- If you want the scheduler to start/stop all instances of an ASG, make sure all ASG-members have the scheduler-tag set and the Min-Value of the ASG is set to 0.
- If you want the scheduler to start/stop all but N instances of an ASG, make sure all ASG-members have the scheduler-tag set and the Min-Value of the ASG is set to N.

# RDS considerations

Not all types of RDS are supported to be started/stopped by the scheduler. Make sure your RDS instance is supported to be started/stopped and check the logs of the scheduler after configuring an RDS to be scheduled. Databases that are in any other state than stopped/available can't be started/stopped.

# CloudWatch metrics

The scheduler creates CloudWatch metrics by default so you can track the state of instances that are started/stopped by the scheduler. A metric value of 1 means the instance is running, a value of 0 means it's stopped.

# Logs

The scheduler writes logs about the actions performed. You can find the logs under CloudWatch -> Logs.

# Author
- Initial version: AWS provided
- Second version by: Eric Ho (https://github.com/hbwork/ec2-scheduler)
- Third version by: Pablo Pinés León
- Current version by: JSC
Last update: April 16, 2019

***

Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/asl/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.
