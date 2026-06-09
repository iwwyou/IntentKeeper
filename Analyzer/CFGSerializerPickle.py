import pickle
import pathlib
from typing import Dict, Union
from Utils.CFG import ContractCFG, LibraryCFG, FunctionCFG


class CFGSerializerPickle:
    """
    Pickle 기반 CFG 직렬화/역직렬화 클래스
    Python 객체를 그대로 저장/로드
    """

    def __init__(self, base_dir: str = None):
        """
        CFGSerializer 초기화

        Args:
            base_dir: 기본 저장/로드 디렉토리 (None이면 프로젝트 루트 기준)
        """
        if base_dir is None:
            self.base_dir = pathlib.Path(__file__).parent.parent
        else:
            self.base_dir = pathlib.Path(base_dir)

        # 서브 디렉토리들
        self.libraries_dir = self.base_dir / "Libraries" / "objectfile"
        self.contracts_dir = self.base_dir / "Contracts"
        self.serialized_dir = self.base_dir / "SerializedCFGs"

    # =================================================================
    # Library CFG Serialization/Deserialization
    # =================================================================

    def save_library_cfg(self, library_cfg: LibraryCFG, library_name: str = None,
                        file_path: str = None,
                        file_level_structs: dict = None,
                        type_aliases: dict = None) -> str:
        """
        라이브러리 CFG를 Pickle 파일로 저장

        Args:
            library_cfg: 저장할 LibraryCFG 객체
            library_name: 라이브러리 이름 (None이면 CFG에서 추출)
            file_path: 저장할 파일 경로 (None이면 기본 경로 사용)
            file_level_structs: file-level struct 정보 (None이면 빈 dict)
            type_aliases: type alias 정보 (None이면 빈 dict)

        Returns:
            저장된 파일 경로
        """
        if library_name is None:
            library_name = getattr(library_cfg, 'library_name', library_cfg.contract_name)

        # 기본 저장 경로 설정
        if file_path is None:
            self.libraries_dir.mkdir(exist_ok=True, parents=True)
            file_path = self.libraries_dir / f"{library_name}.pkl"
        else:
            file_path = pathlib.Path(file_path)
            file_path.parent.mkdir(exist_ok=True, parents=True)

        # Pickle로 직렬화 (dict wrapper: cfg + file_level_structs + type_aliases)
        try:
            with open(file_path, 'wb') as f:
                pickle.dump({"cfg": library_cfg,
                             "file_level_structs": dict(file_level_structs) if file_level_structs else {},
                             "type_aliases": dict(type_aliases) if type_aliases else {}},
                            f, protocol=pickle.HIGHEST_PROTOCOL)

            print(f"[OK] Library '{library_name}' saved to {file_path}")
            return str(file_path)

        except Exception as e:
            raise ValueError(f"Failed to save library '{library_name}': {e}")

    def load_library_cfg(self, library_name: str, file_path: str = None) -> LibraryCFG:
        """
        라이브러리 CFG를 파일에서 로드

        Args:
            library_name: 로드할 라이브러리 이름
            file_path: 로드할 파일 경로 (None이면 기본 경로 사용)

        Returns:
            LibraryCFG 객체 또는 None
        """
        if file_path is None:
            file_path = self.libraries_dir / f"{library_name}.pkl"
        else:
            file_path = pathlib.Path(file_path)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'rb') as f:
                raw = pickle.load(f)
            if isinstance(raw, dict) and "cfg" in raw:
                return raw["cfg"]
            return raw

        except Exception as e:
            print(f"Warning: Failed to load library '{library_name}': {e}")
            return None

    # =================================================================
    # Contract CFG Serialization/Deserialization
    # =================================================================

    def save_contract_cfg(self, contract_cfg: ContractCFG, contract_name: str = None,
                         file_path: str = None,
                         file_level_structs: dict = None,
                         type_aliases: dict = None) -> str:
        """
        컨트랙트 CFG를 Pickle 파일로 저장

        Args:
            contract_cfg: 저장할 ContractCFG 객체
            contract_name: 컨트랙트 이름 (None이면 CFG에서 추출)
            file_path: 저장할 파일 경로 (None이면 기본 경로 사용)
            file_level_structs: file-level struct 정보 (None이면 빈 dict)
            type_aliases: type alias 정보 (None이면 빈 dict)

        Returns:
            저장된 파일 경로
        """
        if contract_name is None:
            contract_name = contract_cfg.contract_name

        # 기본 저장 경로 설정
        if file_path is None:
            self.contracts_dir.mkdir(exist_ok=True, parents=True)
            file_path = self.contracts_dir / f"{contract_name}.pkl"
        else:
            file_path = pathlib.Path(file_path)
            file_path.parent.mkdir(exist_ok=True, parents=True)

        # Pickle로 직렬화 (dict wrapper: cfg + file_level_structs + type_aliases)
        try:
            with open(file_path, 'wb') as f:
                pickle.dump({"cfg": contract_cfg,
                             "file_level_structs": dict(file_level_structs) if file_level_structs else {},
                             "type_aliases": dict(type_aliases) if type_aliases else {}},
                            f, protocol=pickle.HIGHEST_PROTOCOL)

            print(f"[OK] Contract '{contract_name}' saved to {file_path}")
            return str(file_path)

        except Exception as e:
            raise ValueError(f"Failed to save contract '{contract_name}': {e}")

    def load_contract_cfg(self, contract_name: str, file_path: str = None) -> ContractCFG:
        """
        컨트랙트 CFG를 파일에서 로드

        Args:
            contract_name: 로드할 컨트랙트 이름
            file_path: 로드할 파일 경로 (None이면 기본 경로 사용)

        Returns:
            ContractCFG 객체 또는 None
        """
        if file_path is None:
            file_path = self.contracts_dir / f"{contract_name}.pkl"
        else:
            file_path = pathlib.Path(file_path)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'rb') as f:
                raw = pickle.load(f)
            if isinstance(raw, dict) and "cfg" in raw:
                return raw["cfg"]
            return raw

        except Exception as e:
            print(f"Warning: Failed to load contract '{contract_name}': {e}")
            return None

    # =================================================================
    # Batch Operations
    # =================================================================

    def serialize_all_cfgs(self, contract_cfgs: Dict[str, ContractCFG],
                          library_cfgs: Dict[str, LibraryCFG],
                          output_dir: str = None) -> Dict[str, str]:
        """
        모든 CFG를 직렬화하여 파일로 저장

        Args:
            contract_cfgs: 컨트랙트 CFG 딕셔너리
            library_cfgs: 라이브러리 CFG 딕셔너리
            output_dir: 출력 디렉토리 (None이면 기본 디렉토리 사용)

        Returns:
            저장된 파일들의 딕셔너리 {cfg_name: file_path}
        """
        if output_dir is None:
            output_dir = self.serialized_dir
        else:
            output_dir = pathlib.Path(output_dir)

        output_dir.mkdir(exist_ok=True, parents=True)
        saved_files = {}

        # 라이브러리 CFG들 저장
        print(f"Serializing {len(library_cfgs)} libraries...")
        for lib_name, lib_cfg in library_cfgs.items():
            file_path = output_dir / f"{lib_name}_library.pkl"
            try:
                with open(file_path, 'wb') as f:
                    pickle.dump({"cfg": lib_cfg,
                                 "file_level_structs": {},
                                 "type_aliases": {}},
                                f, protocol=pickle.HIGHEST_PROTOCOL)
                saved_files[f"{lib_name}_library"] = str(file_path)
                print(f"  [OK] {lib_name} library")
            except Exception as e:
                print(f"  ✗ Failed to save library {lib_name}: {e}")

        # 컨트랙트 CFG들 저장
        contract_count = 0
        print(f"Serializing contracts...")
        for contract_name, contract_cfg in contract_cfgs.items():
            # 라이브러리는 이미 위에서 처리했으므로 건너뛰기
            if contract_name in library_cfgs:
                continue

            contract_count += 1
            file_path = output_dir / f"{contract_name}_contract.pkl"
            try:
                with open(file_path, 'wb') as f:
                    pickle.dump({"cfg": contract_cfg,
                                 "file_level_structs": {},
                                 "type_aliases": {}},
                                f, protocol=pickle.HIGHEST_PROTOCOL)
                saved_files[f"{contract_name}_contract"] = str(file_path)
                print(f"  [OK] {contract_name} contract")
            except Exception as e:
                print(f"  ✗ Failed to save contract {contract_name}: {e}")

        print(f"Serialization complete: {len(library_cfgs)} libraries, {contract_count} contracts")
        return saved_files

    def load_all_cfgs(self, input_dir: str = None) -> tuple:
        """
        디렉토리에서 모든 CFG 파일을 로드

        Args:
            input_dir: 입력 디렉토리 (None이면 기본 디렉토리 사용)

        Returns:
            (contract_cfgs, library_cfgs) 튜플
        """
        if input_dir is None:
            input_dir = self.serialized_dir
        else:
            input_dir = pathlib.Path(input_dir)

        if not input_dir.exists():
            print(f"Directory {input_dir} does not exist")
            return {}, {}

        contract_cfgs = {}
        library_cfgs = {}

        # Pickle 파일들 찾기
        pkl_files = list(input_dir.glob("*.pkl"))
        print(f"Found {len(pkl_files)} pickle files in {input_dir}")

        for pkl_file in pkl_files:
            try:
                with open(pkl_file, 'rb') as f:
                    raw = pickle.load(f)

                # unwrap dict wrapper (backward compat)
                if isinstance(raw, dict) and "cfg" in raw:
                    cfg = raw["cfg"]
                else:
                    cfg = raw

                # 파일 타입에 따라 분류
                if pkl_file.name.endswith("_library.pkl"):
                    lib_name = pkl_file.stem.replace("_library", "")
                    library_cfgs[lib_name] = cfg
                    print(f"  [OK] Loaded library: {lib_name}")

                elif pkl_file.name.endswith("_contract.pkl"):
                    contract_name = pkl_file.stem.replace("_contract", "")
                    contract_cfgs[contract_name] = cfg
                    print(f"  [OK] Loaded contract: {contract_name}")

                else:
                    # CFG 타입으로 판단
                    if hasattr(cfg, 'library_name'):
                        lib_name = cfg.library_name
                        library_cfgs[lib_name] = cfg
                        print(f"  [OK] Loaded library: {lib_name}")
                    elif hasattr(cfg, 'contract_name'):
                        contract_name = cfg.contract_name
                        contract_cfgs[contract_name] = cfg
                        print(f"  [OK] Loaded contract: {contract_name}")

            except Exception as e:
                print(f"  ✗ Failed to load {pkl_file.name}: {e}")

        print(f"Load complete: {len(contract_cfgs)} contracts, {len(library_cfgs)} libraries")
        return contract_cfgs, library_cfgs
