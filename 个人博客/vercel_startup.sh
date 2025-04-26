#!/bin/bash

# 创建上传目录
mkdir -p ./static/uploads

# 创建临时目录
mkdir -p ./temp

# 输出版本信息（用于调试）
python --version
pip list | grep Flask

echo "Vercel启动脚本执行完成" 