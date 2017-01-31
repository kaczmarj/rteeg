#!/usr/bin/env bash

# Install PyQt5 and its dependency, SIP.
SIP_URL='https://sourceforge.net/projects/pyqt/files/sip/sip-4.19/sip-4.19.tar.gz'
SIP_FILE=$(basename $SIP_URL)

PYQT_URL='https://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-5.7.1/PyQt5_gpl-5.7.1.tar.gz'
PYQT_FILE=$(basename $PYQT_URL)

cd ..

# Download SIP source, and build.
curl -L -O --retry-delay 5 --retry 5 $SIP_URL
tar -xvf $SIP_FILE
cd ${SIP_FILE%.*.*}
python configure.py
make -j 2
sudo make install

cd ..

# Download PyQt5 source, and build.
curl -L -O --retry-delay 5 --retry 5 $PYQT_URL
tar -xvf $PYQT_FILE
cd ${PYQT_FILE%.*.*}
python configure.py --confirm-license
make -j 2
sudo make install

cd ../rteeg

# Test install.
python -c 'from PyQt5 import QtCore, QtGui, QtWidgets'
