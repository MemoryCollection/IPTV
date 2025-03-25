# 使用 Windows Server Core 作为基础镜像，因为工作流在 Windows 上运行
FROM mcr.microsoft.com/windows/servercore:ltsc2019

# 设置工作目录
WORKDIR /app

# 安装 Python 3.9
RUN powershell -Command \
    $ErrorActionPreference = 'Stop'; \
    $retryCount = 3; \
    $retryInterval = 5; \
    for ($i = 0; $i -lt $retryCount; $i++) { \
        try { \
            Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe" -OutFile "python-installer.exe"; \
            break; \
        } catch { \
            if ($i -lt $retryCount - 1) { \
                Write-Host "Download failed, retrying in $retryInterval seconds..."; \
                Start-Sleep -Seconds $retryInterval; \
            } else { \
                throw; \
            } \
        } \
    }; \
    Start-Process .\python-installer.exe -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1' -NoNewWindow -Wait; \
    Remove-Item -Force python-installer.exe

# 安装 vcpkg
RUN powershell -Command \
    if (!(Test-Path -Path 'C:/Tools')) { New-Item -ItemType Directory -Force -Path 'C:/Tools' }; \
    cd C:/Tools; \
    git clone https://github.com/microsoft/vcpkg; \
    .\vcpkg\bootstrap-vcpkg.bat

# 设置环境变量
ENV VCPKG_ROOT=C:/Tools/vcpkg
ENV PATH=%PATH%;C:/Tools/vcpkg

# 安装 Python 依赖项
RUN python -m pip install --upgrade pip
RUN pip install grpcio-tools==1.48.2

# 安装 Visual Studio Build Tools
RUN powershell -Command \
    $ErrorActionPreference = 'Stop'; \
    $retryCount = 3; \
    $retryInterval = 5; \
    for ($i = 0; $i -lt $retryCount; $i++) { \
        try { \
            Invoke-WebRequest -Uri "https://aka.ms/vs/16/release/vs_buildtools.exe" -OutFile "vs_buildtools.exe"; \
            break; \
        } catch { \
            if ($i -lt $retryCount - 1) { \
                Write-Host "Download failed, retrying in $retryInterval seconds..."; \
                Start-Sleep -Seconds $retryInterval; \
            } else { \
                throw; \
            } \
        } \
    }; \
    Start-Process .\vs_buildtools.exe -ArgumentList '--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --quiet --wait' -NoNewWindow -Wait; \
    Remove-Item -Force vs_buildtools.exe
