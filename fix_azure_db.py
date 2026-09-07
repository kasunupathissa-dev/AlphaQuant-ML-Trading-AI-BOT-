import subprocess

script = """#!/usr/bin/env bash
sudo -u postgres psql -c "ALTER USER kazzr WITH PASSWORD 'AlphaQuant2024!';"
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'AlphaQuant2024!';"
sudo systemctl restart aq-dashboard
sudo systemctl restart aq-unified-quant
echo "DATABASE PERMISSIONS CONFIGURED SUCCESSFULLY"
"""

cmd = ['ssh', '-i', 'C:/server/alphaquant-server_key.pem', '-o', 'StrictHostKeyChecking=no', 'kasun@172.160.241.212', 'cat > /tmp/fix_db.sh && bash /tmp/fix_db.sh']
p = subprocess.run(cmd, input=script.encode('utf-8'), capture_output=True)
print('Return code:', p.returncode)
print('Stdout:', p.stdout.decode('utf-8'))
print('Stderr:', p.stderr.decode('utf-8'))
