# Bug #003: Error VERR_ALREADY_EXISTS al importar .ova

**Severidad:** Media
**Módulo:** Entorno / VirtualBox
**Entorno:** Windows 11, VirtualBox 7.x
**Fecha:** 2026-09

## Descripción

Al intentar importar el archivo `.ova` de Whonix, VirtualBox reporta que ya existen archivos con ese nombre.

## Pasos para reproducir

1. Descargar `Whonix-LXQt-18.2.1.9.Intel_AMD64.ova`.
2. `Archivo → Importar servicio virtualizado`.
3. Seleccionar el .ova.
4. Confirmar importación.

## Resultado esperado

VM importada correctamente.

## Resultado obtenido
VERR_ALREADY_EXISTS

text

## Causa raíz

Archivos de disco (`.vdi`) de una importación previa que se interrumpió o se completó parcialmente. VirtualBox detecta que los archivos ya existen en `C:\Users\...\VirtualBox VMs\`.

## Solución aplicada

1. Cerrar VirtualBox completamente.
2. Ir a `C:\Users\<usuario>\VirtualBox VMs\`.
3. Borrar la carpeta `Whonix-Gateway-LXQt` (o similar).
4. Reabrir VirtualBox.
5. Importar de nuevo el .ova.

## Verificación

Importación exitosa sin errores.

## Lección aprendida

Limpiar restos de VMs anteriores antes de reimportar. Documentar este error evita perder tiempo buscando soluciones complejas cuando la causa es simple.
