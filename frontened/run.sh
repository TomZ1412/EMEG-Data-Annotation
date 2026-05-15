echo "正在建立SSH隧道..."
# 后台建立SSH隧道
ssh -4 -L 8000:10.140.37.163:8000 -N zhangchi1@jump.pjlab.org.cn &

echo "等待隧道建立..."
sleep 3

echo "启动React开发服务器..."
npm run dev