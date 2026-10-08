import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation {
    id: presentation

    function onActivate() { }
    function onLeave() { }

    Slide {
        Rectangle {
            anchors.fill: parent
            color: "#121418"
            Text {
                anchors.centerIn: parent
                color: "#FFFFFF"
                font.pixelSize: 24
                horizontalAlignment: Text.AlignHCenter
                text: "Installing Rocket OS 🚀<br/><br/>" +
                      "Windows stays available in the boot menu."
            }
        }
    }
}
