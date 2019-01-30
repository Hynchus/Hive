import subprocess
import os
import sys
import platform

PIP_REQUIREMENTS_FILENAME = "requirements.edy"
# 'additional_requirements' are packages that aren't named the same as their import, or other such reasons
PIP_ADDITIONAL_REQUIREMENTS_FILENAME = "additional_requirements.edy"
CONFLICTING_PACKAGES_FILENAME = "conflicting_packages.edy"


def install_requirements():
    print("Installing requirements")
    
    # # Install dependencies not handled by pip
    # try:
    #     if sys.platform == "linux" or sys.platform == "linux2":
    #         subprocess.check_call(['apt-get', 'update'])
    #         subprocess.check_call(['apt-get', 'install', 'libportaudio2'])
    # except Exception as ex:
    #     print("Could not install portaudio dependencies.")
    #     print(ex)
    #     return False

    # Install dependencies kept locally
    architecture_folder = platform.architecture()[0]
    root_directory = os.path.join(os.path.dirname(__file__), "lib", architecture_folder)
    for current_directory, _, filenames in os.walk(root_directory):
        for filename in filenames:
            if os.path.splitext(filename)[1] == '.whl':
                try:
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', os.path.join(current_directory, filename)])
                except Exception as ex:
                    print("Could not install ", filename)
                    print(ex)
                    return False
    # Install pip dependencies not held locally
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', PIP_REQUIREMENTS_FILENAME])
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', PIP_ADDITIONAL_REQUIREMENTS_FILENAME])
    except Exception as ex:
        print("Could not install pip dependencies.")
        print(ex)
        return False
    return True

def update_requirements():
    print("Updating requirements")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pipreqs'])
    except Exception as ex:
        print("Could not install 'pipreqs'.")
        print(ex)
    # Gather and save requirements
    subprocess.run(['pipreqs', '--force', '--savepath', PIP_REQUIREMENTS_FILENAME, os.path.dirname(__file__)])
    # Remove conflicting packages from requirements file
    conflicts = []
    with open(CONFLICTING_PACKAGES_FILENAME, 'r') as conflicts_file:
        for line in conflicts_file:
            conflicts.append(line)
    requirements = []
    with open(PIP_REQUIREMENTS_FILENAME, 'r') as requirements_file:
        for line in requirements_file:
            if line.split('=')[0] not in conflicts:
                requirements.append(line)
    with open(PIP_REQUIREMENTS_FILENAME, 'w') as requirements_file:
        requirements_file.writelines(requirements)
    return True        