# AWS-CF-EC2RDS-Scheduler

This is a solution to enable the scheduling of EC2 and RDS instances, so that they can be started and stopped automatically. It is composed of the following files:

# ec2rds-scheduler.yaml

It's a CloudFormation template that enables the configuration and usage of the solution. It also creates a lambda function 

# ec2rds-scheduler.py

This file contains auxiliary functions for the lambda function.

# ec2rds-scheduler.zip
Compiled version of the ec2-scheduler.py file with its dependencies

# Instructions

The manual usage of the solution is the following:

1. Upload the ec2rds-scheduler.zip to an s3 bucket
2. Upload the CF template to CloudFormation, provide the name of the s3 bucket where you upload the .zip file and change the parameters as desired, including the possibility of enabling metrics in CloudWatch. The template will trigger the creation of a Lambda function that executes periodically and checks if any EC2 and RDS instances needs to be started or stopped
3. Add tags to the desired instances as explained below
4. You can check that the solution is working by checking the metrics on Cloudwatch, if you have chosen to enable them

# Custom parameters

| Parameter | Default | Notes|
| ------ | ------ |------|
|Schedule | 5 minutes | How often should the lambda function execute|
|DefaultStartTime | 0800 | Default Time to start the tagged instances|
|DefaultStopTime | 1800 | Default Time to stop the tagged instances|
|DefaultDaysActive| 'mon','tue','wed','thu','fri' | You can specify which days the instances should be active, or just enter 'all' |
|DefaultTimeZone | Europe/Zurich | Default time zone for the scheduler|
|CustomTagName | scheduler:ec2-startstop | This tag identifies EC2 instances to receive automated actions|
|CustomRDSTagName | scheduler:rds-startstop | This tag identifies RDS instances to receive automated actions|
|CloudWatchMetrics| Disabled |  |
|Regions | all | AWS regions seperated by space(s) where EC2/RDS scheduler operates|

|RDSSupport | Yes| Change to 'No' to disable RDS instance stop/start support|

|S3BucketName | | S3 Bucket name where Lambda zipfile sits|

||  | |

# How to use it

You can apply custom start and stop parameters to an EC2 or RDS instance which will override the default values you set during initial deployment. To do this, modify the tag value to specify the alternative settings.

The EC2/RDS Scheduler will read tag values, looking for four possible custom parameters in the following order: 
<start time>; <stop time>; <time zone>; <active day(s)>

You can sepereate each values with a semicolon or colon on EC2 instances. On RDS instances colon is the only possibility, it doesn't allow entering semicolons as values for tags. The following table gives acceptable input values for each field

|Tag Value Field|Acceptable input values|Scheduled Action/Note |
| ------ | ------ | ------ | 
|start time | none | No action|
|| 24x7| Start the instance at any time if it is stopped|
|| default| The instance will start and stop on the default schedule|
|| true| The instance will start and stop on the default schedule|
|| HHMM| Time in 24-hour format (Default time zone or timezone specified, with no colon)|
|stop time | none | No action|
|| HHMM| Time in 24-hour format (Default time zone or timezone specified, with no colon)|
|time zone| <empty>| Default scheduler time zone |
||utc| UTC time zone |
||Europe/Zurich| Or any pytz library supported time zone value |
|active day(s)|all| All days |
||weekdays| From Monday to Friday |
||sat,1,2| Saturday, 1st and 2nd in each month|
||sat/2, fri/4| The second Saturday and fourth Friday in each month|

# Example Tag Value

The following table gives examples of different tag values and the resulting Scheduler actions

|Example Tag Value|EC2 Scheduler Action|
|------ | ------|
|24x7 | start RDS/EC2 instance at any time if it is stopped|
|24x5 | start RDS/EC2 instance at DefaultStartTime on Monday, and stop at DefaultStopTime on Friday (DefaultTimeZone) |
|24x5;;Europe/Zurich; | start at DefaultStartTime on Monday, and stop DefaultStopTime on Friday (Europe/Zurich timezone)|
|none | No action|
|default | The instance will start and stop on the default schedule|
|true | The instance will start and stop on the default schedule|
|0800;;;weekdays |Start the instance at 08:00 (Default Timezone) in weekdays if it is stopped|
|;1700;;weekdays |Stop the instance at 17:00 (Default Timezone) in weekdays if it is running.|
|0800;1800;utc;all|The instance will start at 0800 hours and stop at 1800 hours on all days|
|0001;1800;Etc/GMT+1;Mon/1| The instance will start at 0001 hour and stop at 1800 hour (first Monday of every month, Etc/GMT+1 timezone)|
|1000;1700;utc;weekdays | The instance will start at 1000 hours and stop at 1700 hours Monday through Friday.|
|1030;1700;utc;mon,tue,fri| The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday only.|
|1030;1700;utc;mon,tue,fri,1,3 |The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday or date 1,3 only.|
|1030;1700;utc;1 |The instance will start at 1030 hours and stop at 1700 hours on date 1 only.|
|1030;1700;utc;01,fri | The instance will start at 1030 hours and stop at 1700 hours on date 1 and Friday.|
|0815;1745;utc;wed,thu |The instance will start at 0815 hours and stop at 1745 hours on Wednesday and Thursday.|
|none;1800;utc;weekdays| The instance stop at 1800 hours Monday through Friday. |
|0800;none;utc;weekdays| The instance start at 0800 hours Monday through Friday. |
|1030;1700;utc;mon,tue,fri,1,3,sat/1|The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday ,date 1,3 or the first Saturday in every month (utc TimeZone)|
|1030;1700;;mon,tue,fri,1,3,sat/1|The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday ,date 1,3 or the first Saturday in every month (Default TimeZone)|
|1030;1700;Europe/Zurich;mon,tue,fri,1,3,sat/1 | The instance will start at 1030 hours and stop at 1700 hours on Monday, Tuesday, and Friday ,date 1,3 or the first Saturday in every month (Europe/Zurich TimeZone)|


# Author
- Initial version: AWS provided
- Second version by: Eric Ho (https://github.com/hbwork/ec2-scheduler)
- Current version by: Pablo Pinés León
Last update: October 17, 2018

***

Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/asl/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.
