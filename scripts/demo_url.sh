#!/usr/bin/env bash
set -euo pipefail

cluster="${CLUSTER:-sigrif-demo}"
service="${SERVICE:-nginx}"

task_arn=$(aws ecs list-tasks --cluster "$cluster" --service-name "$service" --query 'taskArns[0]' --output text)
eni=$(aws ecs describe-tasks --cluster "$cluster" --tasks "$task_arn" --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
ip=$(aws ec2 describe-network-interfaces --network-interface-ids "$eni" --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
echo "http://$ip"
