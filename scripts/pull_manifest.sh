D=/storage/emulated/0/Android/data/com.netease.dwrg/files/netease/dwrg.common/Documents
O=/data/local/tmp/idvman
rm -rf $O; mkdir -p $O
ls -la $D/thd | head -30
echo "== sizes"
ls -la $D/*.json $D/update.ini
for f in pkgmapping.json static.json preload.json download_pachages.json update.ini; do cp $D/$f $O/ 2>/dev/null; done
ls -la $D/thd | awk '{print $5, $9}' | sort -n | tail -5
cp -r $D/thd $O/thd
chmod -R 755 $O
du -sh $O
