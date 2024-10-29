termux-change-repo --> Simgle Mirror --> Grimler

then

pkg i tur-repo -y && pkg update && pkg upgrade -y && pkg i git wget python3.10 -y && git clone https://github.com/thelisx/termuxHikka ~/Hikka && cd ~/Hikka && python3.10 -m pip install -r requirements.txt && python3.10 -m hikka
