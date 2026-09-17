# Bug #001: Pantalla negra en Whonix Workstation tras reinicio

**Severidad:** Alta
**Módulo:** Entorno / VirtualBox
**Entorno:** Linux Mint, VirtualBox 7.x, Whonix Workstation 18.x
**Fecha:** 2026-09

## Descripción

Después de reiniciar la Workstation (o de instalar Guest Additions), la pantalla se queda negra. La VM no responde a `Ctrl+Alt+F2`, `Ctrl+Alt+F3`.

## Pasos para reproducir

1. Iniciar Whonix Workstation.
2. Instalar Guest Additions: `sudo apt install virtualbox-guest-x11`.
3. Reiniciar la VM.
4. Esperar 2-3 minutos.

## Resultado esperado

Escritorio de XFCE visible tras el reinicio.

## Resultado obtenido

Pantalla negra permanente. Sin cursor, sin respuesta a atajos de teclado.

## Causa raíz

Conflicto entre los drivers de video de VirtualBox y el entorno gráfico de Whonix. La **Aceleración 3D** activada por defecto causa que el servidor gráfico (Xorg) no arranque correctamente.

## Solución aplicada

1. Apagar la VM con `Máquina → Apagar → Terminar proceso`.
2. En VirtualBox: `Configuración → Pantalla`.
3. **Desactivar** Aceleración 3D.
4. **Cambiar** Controlador de Video a `VMSVGA`.
5. **Memoria de Video:** 128 MB.
6. Iniciar de nuevo.

## Verificación

Tras aplicar los cambios, la Workstation arranca correctamente y muestra el escritorio XFCE.

## Lección aprendida

- La Aceleración 3D en VirtualBox es problemática para VMs Linux ligeras.
- Siempre desactivarla en Whonix antes de la primera instalación.
- Documentar la configuración de video desde el primer día evita horas de troubleshooting.
