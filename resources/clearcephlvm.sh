for i in `lvs | grep osd | awk '{print $1" "$2}'`
do
    lvremove -f $i
done

for i in `vgs | grep ceph | awk '{print $1}'`
do
    vgremove -f $i
done

for i in `pvs | grep ceph | awk '{print $1}'`
do
    pvremove -f $i
done
