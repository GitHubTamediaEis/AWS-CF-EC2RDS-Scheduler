In case you decide to modify the contents of the .py file you will need to create a new .zip file and upload it to the S3 bucket. Make sure that you also modify and update the CloudFormation template accordingly.

Then, from a linux machine, you just need to follow this steps to create a new package:

1. Copy the .py to an empty directory and enter that directory
2. Execute pip install pytz -t . (you might need to install pip beforehand). This will copy the contents of the pytz package on the current directory
3. Create a zip file executing zip -r -9 ../ec2-scheduler.zip *
4. The zip file is ready to be uploaded to the S3 bucket 
