# Bug #004: Error E_ACCESSDENIED y No raw-mode support

**Severidad:** Crítica
**Módulo:** Entorno / VirtualBox + Windows
**Entorno:** Windows 11, VirtualBox 7.x, CPU AMD
**Fecha:** 2026-09

## Descripción

VirtualBox no puede iniciar la VM. Error `0x80070005` y `No raw-mode support in this build!`. La VM se queda en negro o se cierra inmediatamente.

## Pasos para reproducir

1. Iniciar Whonix Gateway en VirtualBox.
2. Esperar el arranque.

## Resultado esperado

VM arranca normalmente.

## Resultado obtenido
GIM: KVM: Resetting MSRs
NEM: Destroying partition ...
ERROR [COM]: aRC=E_ACCESSDENIED (0x80070005)
fHwMForce=true - No raw-mode support in this build!

text

## Causa raíz

Windows 11 bloquea el acceso de VirtualBox a la virtualización por hardware mediante:
1. **Integridad de Memoria** (Core Isolation).
2. **Hyper-V** activo en segundo plano (incluso si no se usa).
3. **VirtualMachinePlatform** y **WSL2** interfiriendo.
4. Antivirus de terceros (Avast, Norton, McAfee).

## Solución aplicada

1. **Desactivar Integridad de Memoria:**
   - `Seguridad de Windows → Seguridad del dispositivo → Aislamiento del núcleo → Integridad de memoria → Apagar`.
   - Reiniciar obligatorio.

2. **Desactivar Hyper-V desde CMD como Admin:**
   ```cmd
   bcdedit /set hypervisorlaunchtype off
   dism.exe /Online /Disable-Feature /FeatureName:Microsoft-Hyper-V-All
   dism.exe /Online /Disable-Feature /FeatureName:VirtualMachinePlatform
   dism.exe /Online /Disable-Feature /FeatureName:Microsoft-Windows-Subsystem-Linux
Verificar SVM Mode en BIOS:

Lenovo: F2 o Novo button → Configuration → SVM Mode → Enabled.

Reiniciar Windows.

Verificación
Administrador de tareas → Rendimiento → CPU → Virtualización: Habilitado.

VM arranca sin errores.

Lección aprendida
Windows 11 bloquea la virtualización por defecto. Documentar los 4 pasos ahorra horas. Siempre revisar esto primero antes de pensar que VirtualBox está roto.
