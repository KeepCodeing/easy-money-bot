#!/bin/bash

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 检查是否安装了 cron
if ! command -v crontab &> /dev/null; then
    echo "cron is not installed. Please install it first."
    exit 1
fi

# 确保日志目录存在
LOGS_DIR="${SCRIPT_DIR}/logs/cron"
mkdir -p "$LOGS_DIR"

# 创建临时文件来存储现有的 crontab 内容
TEMP_CRON=$(mktemp)
crontab -l > "$TEMP_CRON" 2>/dev/null

# 添加注释标记
echo "# CS2Market Bot Tasks - Added $(date '+%Y-%m-%d %H:%M:%S')" >> "$TEMP_CRON"

# 添加环境变量设置（如果使用虚拟环境，取消下面的注释并修改路径）
# echo "VIRTUAL_ENV=${SCRIPT_DIR}/venv" >> "$TEMP_CRON"
# echo "PATH=${SCRIPT_DIR}/venv/bin:\$PATH" >> "$TEMP_CRON"

# 添加爬虫任务 (10:00, 14:00, 18:00, 22:00, 02:00, 06:00)
echo "0 10 * * * cd ${SCRIPT_DIR} && python main.py crawl --indicator boll >> ${LOGS_DIR}/crawl_\$(date +\%Y\%m\%d_10).log 2>&1" >> "$TEMP_CRON"
echo "0 14 * * * cd ${SCRIPT_DIR} && python main.py crawl --indicator boll >> ${LOGS_DIR}/crawl_\$(date +\%Y\%m\%d_14).log 2>&1" >> "$TEMP_CRON"
echo "0 18 * * * cd ${SCRIPT_DIR} && python main.py crawl --indicator boll >> ${LOGS_DIR}/crawl_\$(date +\%Y\%m\%d_18).log 2>&1" >> "$TEMP_CRON"
echo "0 22 * * * cd ${SCRIPT_DIR} && python main.py crawl --indicator boll >> ${LOGS_DIR}/crawl_\$(date +\%Y\%m\%d_22).log 2>&1" >> "$TEMP_CRON"
echo "0 2 * * * cd ${SCRIPT_DIR} && python main.py crawl --indicator boll >> ${LOGS_DIR}/crawl_\$(date +\%Y\%m\%d_02).log 2>&1" >> "$TEMP_CRON"
echo "0 6 * * * cd ${SCRIPT_DIR} && python main.py crawl --indicator boll >> ${LOGS_DIR}/crawl_\$(date +\%Y\%m\%d_06).log 2>&1" >> "$TEMP_CRON"

# 添加排名任务 (09:00, 21:00)
echo "0 9 * * * cd ${SCRIPT_DIR} && python main.py rank --notify >> ${LOGS_DIR}/rank_\$(date +\%Y\%m\%d_09).log 2>&1" >> "$TEMP_CRON"
echo "0 21 * * * cd ${SCRIPT_DIR} && python main.py rank --notify >> ${LOGS_DIR}/rank_\$(date +\%Y\%m\%d_21).log 2>&1" >> "$TEMP_CRON"

# 添加日志清理任务（保留7天的日志）
echo "0 0 * * * find ${LOGS_DIR} -name \"*.log\" -mtime +7 -delete" >> "$TEMP_CRON"

# 添加结束标记
echo "# End of CS2Market Bot Tasks" >> "$TEMP_CRON"

# 安装新的 crontab
crontab "$TEMP_CRON"

# 删除临时文件
rm "$TEMP_CRON"

echo "Cron jobs have been set up successfully with logging!"
echo "Logs will be stored in: ${LOGS_DIR}"
echo "Log files will be automatically cleaned up after 7 days"
echo ""
echo "You can check the current cron jobs by running: crontab -l"
echo ""
echo "To monitor the logs in real-time, you can use:"
echo "tail -f ${LOGS_DIR}/crawl_*.log"
echo "tail -f ${LOGS_DIR}/rank_*.log"
echo ""
echo "To test the commands immediately, you can run:"
echo "cd ${SCRIPT_DIR} && python main.py crawl --indicator boll"
echo "cd ${SCRIPT_DIR} && python main.py rank --notify"

# 设置日志目录的权限
chmod 755 "$LOGS_DIR" 