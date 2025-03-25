# 使用 Windows Server Core 作为基础镜像
FROM mcr.microsoft.com/windows/servercore:ltsc2022

# 安装 Chocolatey 包管理器
RUN @"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))" && SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"

# 安装 Visual Studio Build Tools 2019
RUN choco install visualstudio2019buildtools --package-parameters "--add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows10SDK.19041" -y

# 安装 Python 3.9
RUN choco install python --version=3.9 -y

# 设置环境变量
ENV PYTHONIOENCODING=utf-8

# 安装 Python 依赖项
RUN python -m pip install --upgrade pip
RUN pip install grpcio-tools==1.48.2

# 安装 vcpkg
RUN git clone https://github.com/microsoft/vcpkg C:\Tools\vcpkg
RUN C:\Tools\vcpkg\bootstrap-vcpkg.bat
ENV VCPKG_ROOT=C:\Tools\vcpkg
RUN C:\Tools\vcpkg\vcpkg integrate install

# 设置工作目录
WORKDIR C:/workspace
