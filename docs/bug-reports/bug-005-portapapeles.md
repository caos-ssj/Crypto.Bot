
Bug #005: Portapapeles no funciona entre Windows y Whonix
Severidad: Media
Módulo: Entorno / VirtualBox Guest Additions
Entorno: Windows 11 host, Whonix Workstation guest
Fecha: 2026-09

Descripción
Copiar texto en Windows y pegarlo en Whonix (o viceversa) no funciona, aunque la opción "Portapapeles compartido" esté en Bidireccional.

Pasos para reproducir
Copiar texto en Windows (Ctrl+C).

Ir a Whonix Workstation.

Pegar (Ctrl+V).

Resultado esperado
El texto aparece pegado en la VM.

Resultado obtenido
No pasa nada. El portapapeles de la VM está vacío.

Causa raíz
Falta instalar las Guest Additions dentro de la VM. VirtualBox necesita un "puente" de software en el guest para permitir la comunicación del portapapeles.

Solución aplicada
Opción A (recomendada):

bash
sudo apt update
sudo apt install virtualbox-guest-x11 virtualbox-guest-utils virtualbox-guest-dkms
sudo reboot
Opción B (si falla):
No forzarlo. Usar archivos de texto compartidos o escribir los enlaces manualmente.

Verificación
En VirtualBox, pestaña "Atributos de tiempo de ejecución" debe decir "Complementos del invitado: Detectado".

Copiar/pegar funciona entre host y guest.

Lección aprendida
El portapapeles compartido es un riesgo de seguridad (malware en la VM podría leer datos del host).

Nunca copiar contraseñas o datos bancarios hacia la VM.

Solo usar para enlaces públicos, textos de investigación o comandos.
