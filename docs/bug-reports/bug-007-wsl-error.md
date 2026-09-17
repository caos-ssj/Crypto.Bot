
Bug #007: Error 0x800f080c al desactivar WSL
Severidad: Baja
Módulo: Windows / DISM
Entorno: Windows 11
Fecha: 2026-09

Descripción
Al ejecutar dism.exe /Disable-Feature /FeatureName:Microsoft-Windows-Subsystem-Linux, el sistema devuelve error.

Pasos para reproducir
CMD como Administrador.

Ejecutar:

cmd
dism.exe /Online /Disable-Feature /FeatureName:Microsoft-Windows-Subsystem-Linux
Resultado esperado
WSL desactivado correctamente.

Resultado obtenido
text
Error: 0x800f080c
Feature name Microsoft-Windows-Subsystem-Linux is unknown.
Causa raíz
WSL ya estaba desactivado, o el nombre del componente cambió en esa versión de Windows. El comando busca un componente que no existe.

Solución aplicada
Ignorar el error. No es crítico. El comando importante es:

cmd
bcdedit /set hypervisorlaunchtype off
Ese es el que libera la virtualización para VirtualBox.

Verificación
El comando bcdedit /enum {current} debe mostrar:

text
hypervisorlaunchtype    Off
Lección aprendida
No todos los errores son críticos. Identificar el comando clave (en este caso bcdedit) y no bloquearse con errores secundarios.
