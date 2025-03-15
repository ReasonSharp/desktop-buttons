#!/bin/bash
# install.sh - Installs the desktop-buttons project

# Configurable vars
INSTALL_DIR="/opt/desktop-buttons"
DESKTOP_DIR="$HOME/.local/share/applications"
URI_HANDLER="$HOME/.local/share/applications/desktop-handler.desktop"
BASE_DIR="${BASE:-/base}"  # Respect your $BASE env var
USERNAME=$(whoami)
GROUPNAME=$(id -gn)
echo $DESKTOP_DIR
echo $URI_HANDLER

# Ensure dependencies (adjust for your distro)
sudo apt update
if ! command -v konsole >/dev/null 2>&1; then
 echo "Installing konsole (edit this if you use a different terminal)..."
 sudo apt install -y konsole
fi
if ! command -v psql >/dev/null 2>&1; then
 echo "Installing PostgreSQL..."
 sudo apt install -y postgresql postgresql-contrib
 sudo systemctl start postgresql
 sudo systemctl enable postgresql
fi
if ! command -v python3 >/dev/null 2>&1; then
 echo "Installing Python3..."
 sudo apt install -y python3
fi
if ! command -v pip3 >/dev/null 2>&1; then
 echo "Installing pip3..."
 sudo apt install -y python3-pip
fi
if ! python3 -c "import flask" >/dev/null 2>&1; then
 echo "Installing Flask..."
 sudo apt install -y python3-flask
fi
if ! python3 -c "import psycopg2" >/dev/null 2>&1; then
 echo "Installing psycopg2..."
 sudo apt install -y python3-psycopg2
fi

# Init DB - either from environment variable $PASSWORD or file $HOME/.pgpass, save to $HOME/.pgpass if not exists
if [ -z $PASSWORD ]; then
 if [ -f "${HOME}/.pgpass" ]; then
  PASSWORD=$(cut -d':' -f5 "${HOME}/.pgpass")
 else
  PASSWORD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c $((16 + RANDOM % 17)))
  echo "localhost:5432:basedb:nikola:$PASSWORD" > "${HOME}/.pgpass"
  chmod 600 "${HOME}/.pgpass"
 fi
fi
cd /tmp && sudo -u postgres psql -c 'CREATE DATABASE basedb;' 2>/dev/null || {
 if sudo -u postgres psql -c "\l" | grep -q "basedb"; then
  echo "'basedb' exists, skipping"
 else
  echo "error: failed to create or verify 'basedb'"
  exit 1
 fi
}
cd - >/dev/null
cd /tmp && sudo -u postgres psql -q -c "DO \$\$ BEGIN CREATE USER \"$USERNAME\" WITH PASSWORD '$PASSWORD'; EXCEPTION WHEN duplicate_object THEN ALTER USER \"$USERNAME\" WITH PASSWORD '$PASSWORD'; END \$\$;" 2>/dev/null || {
 echo "error: failed to create user '$USERNAME' or change password"
 exit 1
}
cd - >/dev/null
cd /tmp && sudo -u postgres psql -q -c "GRANT ALL PRIVILEGES ON DATABASE basedb TO \"$USERNAME\";" >/dev/null || {
 echo "error: failed to grant 'basedb' privileges to '$USERNAME'"
}
cd - >/dev/null
cd /tmp && sudo -u postgres psql -d basedb -q -c "GRANT ALL ON SCHEMA public TO \"$USERNAME\";" >/dev/null || {
 echo "error: failed to grant schema privileges to '$USERNAME'"
 exit 1
}
cd - >/dev/null
cd /tmp && sudo -u postgres psql -d basedb -q -c "ALTER DATABASE basedb OWNER TO \"$USERNAME\";" >/dev/null || {
 echo "error: failed to set 'basedb' owner to '$USERNAME'"
 exit 1;
}
cd - >/dev/null
psql -U "$USERNAME" -d basedb -h localhost -f db-init.sql -q || {
 echo "error: failed to init 'basedb' schema"
 exit 1
}

# Install files
pwd
echo "Installing to $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp desktop.html style.css server.py handler.py "$INSTALL_DIR/"
sudo chmod -R 755 "$INSTALL_DIR"
sudo chmod +x "$INSTALL_DIR/server.py" "$INSTALL_DIR/handler.py"

# Set up URI handler for desktop://
echo "Setting up desktop:// URI handler..."
cat > "$URI_HANDLER" << EOL
[Desktop Entry]
Type=Application
Name=Desktop Button Handler
Exec=/bin/bash -c "cd \$(echo %u | sed 's|^desktop://||') && konsole"
NoDisplay=true
MimeType=x-scheme-handler/desktop;
EOL
chmod +x "$URI_HANDLER"
update-desktop-database "$DESKTOP_DIR"

# Set up systemd service for boot
echo "Setting up systemd service to start server at boot..."
sudo bash -c "cat > /etc/systemd/system/desktop-buttons.service" << EOL
[Unit]
Description=Desktop Buttons HTTP Server
After=network.target local-fs.target postgresql.service

[Service]
ExecStart=$INSTALL_DIR/server.py
Restart=always
WorkingDirectory=$INSTALL_DIR

[Install]
WantedBy=multi-user.target
EOL

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable desktop-buttons.service
sudo systemctl start desktop-buttons.service

echo "Installation complete! Check 'systemctl status desktop-buttons.service'."
