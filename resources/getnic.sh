for i in `ls /sys/class/net`
do
    s=`ip -4 addr show $i | grep inet | grep $1`
    if [ -n "$s" ]
    then
        echo $i
        break
    fi
done
