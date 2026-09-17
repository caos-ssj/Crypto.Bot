
Bug #008: VM se queda en negro pero no se cierra
Severidad: Media
Módulo: Entorno / VirtualBox
Entorno: Windows 11, VirtualBox 7.x
Fecha: 2026-09

Descripción
La VM arranca (no se apaga) pero la pantalla queda completamente negra. Sin texto, sin cursor.

Pasos para reproducir
Iniciar Whonix Workstation.

Esperar el arranque completo (2-3 min).

Resultado esperado
Escritorio de XFCE visible.

Resultado obtenido
Pantalla negra permanente. La VM sigue encendida (no se cierra).

Causa raíz
Problema de visualización gráfica, no de arranque. El sistema operativo está corriendo pero Xorg no puede mostrar el escritorio por conflicto de drivers de video.

Solución aplicada
Diagnóstico primero:

Si el menú de VirtualBox responde → la VM está viva, solo la ventana gráfica falló.

Solución:

Presionar Ctrl+Alt+F1 dentro de la ventana (o F2, F3).

Debería aparecer login en texto: user / user.

Si entra, reiniciar el entorno gráfico:

bash
sudo systemctl restart lightdm
o

bash
sudo systemctl restart display-manager
Volver con Ctrl+Alt+F7.

Solución definitiva:

Apagar la VM.

Configuración → Pantalla → Desactivar Aceleración 3D.

Controlador de Video: VMSVGA.

Memoria de Video: 128 MB.

Reiniciar.

Verificación
Escritorio XFCE visible.

VM responde a comandos.

Lección aprendida
La VM puede estar viva aunque la pantalla esté negra.

La Aceleración 3D es la causa #1 de pantallas negras en VMs Linux.

Siempre tener un snapshot antes de cambios críticos para poder revertir.
