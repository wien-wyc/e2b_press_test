#测试代码说明
#单进程创建100个sandbox , 创建完毕后每sleep 1秒，改变其中20%的sandbox状态
#改变状态的规则
#  运行的sandbox则执行停止操作
#  停止的sanbox则执行恢复操作,并且在sandbox 执行一个ls /home/user,  并且上传一个hello.py或者pi.py执行
#该程序会生成report_{pid}.csv

#CSV取最后三行即可
#timestamp,operation,count,p99,p90,avg
#2025-03-27 11:26:44,create,1076,0.5890,0.3638,0.2563
#2025-03-27 11:26:44,pause,439,8.4534,7.0841,5.4914
#2025-03-27 11:26:44,resume,281,0.3927,0.2276,0.1386

sudo su ubuntu
cd ~/sdk_client
. .venv/bin/activate
./start-us-east.sh 100