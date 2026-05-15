import os
import io
import mne
import torch
from tqdm import tqdm
from constant import MOUNT_DATA_ROOT_PATH, S3_DATA_ROOT_PATH

BRAIN_EXTENSION = ["con", "fif", "set", "bdf", "edf", "vhdr", "ds"]
BRAIN_READ_FUNC_DICT = {
    "fif": mne.io.read_raw_fif,
    "con": mne.io.read_raw_kit,
    "bdf": mne.io.read_raw_bdf,
    "edf": mne.io.read_raw_edf,
    "vhdr": mne.io.read_raw_brainvision,
    "ds": mne.io.read_raw_ctf,
    "set": mne.io.read_raw_eeglab,
    "cnt": mne.io.read_raw_cnt,
    "gdf": mne.io.read_raw_gdf,
}


def is_useful_path(x):
    if "empty" in x or "noise" in x or '"split-02_meg.fif' in x or "hz.ds" in x:
        return False
    return True


def load_torch_warpper(path):
    return torch.load(path, weights_only=True)


def write_torch_warpper(data, path):
    torch.save(data, path)


class DataAccessor:
    def __init__(self, init_client: bool = False, read_only: bool = True):
        if init_client:
            from petrel_client.client import Client

            self.client = Client("~/petreloss.conf")
            self.data_root_path = S3_DATA_ROOT_PATH
        else:
            self.data_root_path = MOUNT_DATA_ROOT_PATH

        self.init_client = init_client
        self.read_only = read_only
        self.place_holder = "PLACE_HOLDER/"
        # self.data_root_path = 

    def search_brain_files(self, root_path: str):
        brain_files = []
        assert not self.init_client
        for root, dir, name in tqdm(os.walk(root_path)):
            if len(name) > 0:
                for i in name:
                    if i.split(".")[-1] in BRAIN_EXTENSION and is_useful_path(i):
                        brain_files.append(
                            {
                                "path": os.path.join(root, i),
                                "dataset": self.get_dataset_folder_name(root),
                            }
                        )
            if len(dir) > 0:
                for i in dir:
                    if i.split(".")[-1] == "ds" and is_useful_path(i):
                        brain_files.append(
                            {
                                "path": os.path.join(root, i),
                                "dataset": self.get_dataset_folder_name(root),
                            }
                        )
        brain_files = [i for i in brain_files if "derivative" not in i["path"]]
        return brain_files

    def convert_path_to_placeholder(self, path: str):
        return path.replace(self.data_root_path, self.place_holder)

    def convert_placeholder_to_path(self, path: str):
        return path.replace(self.place_holder, self.data_root_path)

    def read_brain_file(self, brain_file, preload: bool = True):
        assert not self.init_client
        if isinstance(brain_file, mne.io.BaseRaw):
            return brain_file
        extension = brain_file.rsplit(".")[-1]
        return BRAIN_READ_FUNC_DICT[extension](
            brain_file, verbose=False, preload=preload
        )

    def get_usage_folder_name(self, path: str):
        return path.replace(self.data_root_path, "").split("/")[0]

    def get_dataset_folder_name(self, path: str):
        return path.replace(self.data_root_path, "").split("/")[2]

    def replace_usage_folder_name(self, path: str, new_usage: str):
        return path.replace(f"/{self.get_usage_folder_name(path)}/", f"/{new_usage}/")

    def exist(self, path: str):
        if self.init_client:
            return self.client.contains(path)
        return os.path.exists(path)

    def read(self, path: str, read_func):
        assert self.exist(path)
        if self.init_client:
            with io.BytesIO(self.client.get(path)) as f:
                return read_func(f)
        return read_func(path)

    def write(self, data, path: str, write_func=write_torch_warpper):
        if self.read_only or self.get_usage_folder_name(path) in [
            "raw",
            "evaluate",
        ]:
            return None
        if self.exist(path):
            self.remove(path)

        if self.init_client:
            with io.BytesIO() as f:
                write_func(data, f)
                self.client.put(path, f.getvalue(), update_cache=False)
        else:
            write_func(data, path)

    def remove(self, path):
        if self.read_only:
            return None
        assert self.exist(path)
        if self.init_client:
            self.client.delete(path)
        else:
            os.remove(path)
