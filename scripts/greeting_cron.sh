#!/bin/bash
# 每日早安问候脚本
# 由 crontab 每天9:00触发

DATE=$(date '+%Y-%m-%d %A')
HOUR=$(date '+%H')

# 判断时段
if [ "$HOUR" -ge 5 ] && [ "$HOUR" -lt 12 ]; then
  GREETING="早安"
elif [ "$HOUR" -ge 12 ] && [ "$HOUR" -lt 18 ]; then
  GREETING="午安"
else
  GREETING="晚安"
fi

# 星期几
WEEKDAY=$(date '+%A')

echo "🌅 $GREETING！今天是 $DATE"
echo "☀️ 新的一天已经开始，愿你今天充满能量和好心情！"
echo ""
echo "📋 今日提示："
case $WEEKDAY in
  Monday|星期一)    echo "  · 新的一周，规划好本周目标" ;;
  Tuesday|星期二)   echo "  · 持续推进，保持节奏" ;;
  Wednesday|星期三) echo "  · 一周过半，加油坚持" ;;
  Thursday|星期四)  echo "  · 接近周末，冲刺收尾" ;;
  Friday|星期五)    echo "  · 最后一天，完美收官" ;;
  Saturday|星期六)  echo "  · 周末愉快，好好放松" ;;
  Sunday|星期日)    echo "  · 休息充电，为新周做准备" ;;
esac
echo ""
echo "💪 一起加油！"
