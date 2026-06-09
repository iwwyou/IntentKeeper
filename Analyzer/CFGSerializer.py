import json
import pathlib
from typing import Dict, Any, Union
from Utils.CFG import ContractCFG, LibraryCFG, FunctionCFG, CFGNode


class CFGSerializer:
    """
    CFG 객체들의 직렬화/역직렬화를 담당하는 클래스
    ContractAnalyzer의 직렬화 책임을 분리하여 관리
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
        self.libraries_dir = self.base_dir / "Libraries"
        self.contracts_dir = self.base_dir / "Contracts"
        self.serialized_dir = self.base_dir / "SerializedCFGs"

    # =================================================================
    # Library CFG Serialization/Deserialization
    # =================================================================
    
    def save_library_cfg(self, library_cfg: LibraryCFG, library_name: str = None, file_path: str = None) -> str:
        """
        라이브러리 CFG를 JSON 파일로 저장
        
        Args:
            library_cfg: 저장할 LibraryCFG 객체
            library_name: 라이브러리 이름 (None이면 CFG에서 추출)
            file_path: 저장할 파일 경로 (None이면 기본 경로 사용)
            
        Returns:
            저장된 파일 경로
        """
        if library_name is None:
            library_name = getattr(library_cfg, 'library_name', library_cfg.contract_name)
        
        # 기본 저장 경로 설정
        if file_path is None:
            self.libraries_dir.mkdir(exist_ok=True, parents=True)
            file_path = self.libraries_dir / f"{library_name}.json"
        else:
            file_path = pathlib.Path(file_path)
            file_path.parent.mkdir(exist_ok=True, parents=True)
            
        # LibraryCFG를 직렬화
        serialized_data = self._serialize_library_cfg(library_cfg)
        # 추가: 안전화
        serialized_data = self._json_safe(serialized_data)
        
        # JSON 파일로 저장
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(serialized_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Library '{library_name}' saved to {file_path}")
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
            file_path = self.libraries_dir / f"{library_name}.json"
        else:
            file_path = pathlib.Path(file_path)
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                serialized_data = json.load(f)
            
            # 역직렬화하여 LibraryCFG 객체 생성
            library_cfg = self._deserialize_library_cfg(serialized_data)
            return library_cfg
            
        except Exception as e:
            print(f"Warning: Failed to load library '{library_name}': {e}")
            return None

    def _serialize_library_cfg(self, library_cfg: LibraryCFG) -> Dict[str, Any]:
        """
        LibraryCFG를 직렬화 가능한 dict로 변환
        CFG 클래스의 serialize_for_storage 메서드 활용
        """
        if hasattr(library_cfg, 'serialize_for_storage'):
            return library_cfg.serialize_for_storage()
        
        # 호환성을 위한 기본 직렬화
        serialized = {
            "library_name": getattr(library_cfg, 'library_name', library_cfg.contract_name),
            "functions": {},
            "type": "LibraryCFG"
        }
        
        # 함수들 직렬화
        for func_name, func_cfg in library_cfg.functions.items():
            serialized["functions"][func_name] = self._serialize_function_cfg(func_cfg)
            
        return serialized

    def _deserialize_library_cfg(self, data: Dict[str, Any]) -> LibraryCFG:
        """직렬화된 데이터에서 LibraryCFG 객체를 생성"""
        library_name = data["library_name"]
        library_cfg = LibraryCFG(library_name)
        
        # 함수들 역직렬화
        for func_name, func_data in data.get("functions", {}).items():
            func_cfg = self._deserialize_function_cfg(func_data, library_cfg)
            library_cfg.add_function_cfg(func_name, func_cfg)
            
        return library_cfg

    # =================================================================
    # Contract CFG Serialization/Deserialization
    # =================================================================
    
    def save_contract_cfg(self, contract_cfg: ContractCFG, contract_name: str = None, file_path: str = None) -> str:
        """
        컨트랙트 CFG를 JSON 파일로 저장
        
        Args:
            contract_cfg: 저장할 ContractCFG 객체
            contract_name: 컨트랙트 이름 (None이면 CFG에서 추출)
            file_path: 저장할 파일 경로 (None이면 기본 경로 사용)
            
        Returns:
            저장된 파일 경로
        """
        if contract_name is None:
            contract_name = contract_cfg.contract_name
        
        # 기본 저장 경로 설정
        if file_path is None:
            self.contracts_dir.mkdir(exist_ok=True, parents=True)
            file_path = self.contracts_dir / f"{contract_name}.json"
        else:
            file_path = pathlib.Path(file_path)
            file_path.parent.mkdir(exist_ok=True, parents=True)
            
        # ContractCFG를 직렬화
        serialized_data = self._serialize_contract_cfg(contract_cfg)
        serialized_data = self._json_safe(serialized_data)
        
        # JSON 파일로 저장
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(serialized_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Contract '{contract_name}' saved to {file_path}")
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
            file_path = self.contracts_dir / f"{contract_name}.json"
        else:
            file_path = pathlib.Path(file_path)
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                serialized_data = json.load(f)
            
            # 역직렬화하여 ContractCFG 객체 생성
            contract_cfg = self._deserialize_contract_cfg(serialized_data)
            return contract_cfg
            
        except Exception as e:
            print(f"Warning: Failed to load contract '{contract_name}': {e}")
            return None

    def _serialize_contract_cfg(self, contract_cfg: ContractCFG) -> Dict[str, Any]:
        """
        ContractCFG를 직렬화 가능한 dict로 변환
        CFG 클래스의 serialize_for_storage 메서드 활용
        """
        if hasattr(contract_cfg, 'serialize_for_storage'):
            return contract_cfg.serialize_for_storage()
        
        # 호환성을 위한 기본 직렬화
        serialized_functions = {}
        for func_name, func_cfg in contract_cfg.functions.items():
            serialized_functions[func_name] = self._serialize_function_cfg(func_cfg)
        
        return {
            "cfg_type": contract_cfg.cfg_type,
            "contract_name": contract_cfg.contract_name,
            "functions": serialized_functions,
            "type": "ContractCFG"
        }

    def _deserialize_contract_cfg(self, data: Dict[str, Any]) -> ContractCFG:
        """직렬화된 데이터에서 ContractCFG 객체를 생성"""
        contract_name = data["contract_name"]
        contract_cfg = ContractCFG(contract_name)
        
        # 함수들 역직렬화
        if "functions" in data:
            for func_name, func_data in data["functions"].items():
                func_cfg = self._deserialize_function_cfg(func_data, contract_cfg)
                contract_cfg.add_function_cfg(func_name, func_cfg)
            
        return contract_cfg

    # =================================================================
    # Function CFG Serialization/Deserialization
    # =================================================================
    
    def _serialize_function_cfg(self, func_cfg: FunctionCFG) -> Dict[str, Any]:
        """
        FunctionCFG를 직렬화 가능한 dict로 변환
        CFG 클래스의 serialize_for_storage 메서드 활용
        """
        if hasattr(func_cfg, 'serialize_for_storage'):
            return func_cfg.serialize_for_storage()
        
        # 호환성을 위한 기본 직렬화
        return {
            "function_name": func_cfg.function_name,
            "function_type": getattr(func_cfg, 'function_type', 'function'),
            "parameters": getattr(func_cfg, 'parameters', []),
            "return_types": getattr(func_cfg, 'return_types', []),
        }

    def _deserialize_function_cfg(self, data: Dict[str, Any], parent_cfg: Union[ContractCFG, LibraryCFG]) -> FunctionCFG:
        """직렬화된 데이터에서 FunctionCFG 객체를 생성"""
        # 간단한 FunctionCFG 생성 (실제로는 더 복잡할 수 있음)
        func_cfg = FunctionCFG(
            function_type=data.get("function_type", "function"),
            function_name=data.get("function_name")
        )
        func_cfg.parameters = data.get("parameters", [])
        func_cfg.return_types = data.get("return_types", [])
        
        return func_cfg

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
            file_path = output_dir / f"{lib_name}_library.json"
            try:
                serialized_data = self._serialize_library_cfg(lib_cfg)
                serialized_data = self._json_safe(serialized_data)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(serialized_data, f, indent=2, ensure_ascii=False)
                saved_files[f"{lib_name}_library"] = str(file_path)
                print(f"  ✓ {lib_name} library")
            except Exception as e:
                print(f"  ✗ Failed to save library {lib_name}: {e}")
        
        # 컨트랙트 CFG들 저장 (라이브러리가 아닌 것만)
        contract_count = 0
        print(f"Serializing contracts...")
        for contract_name, contract_cfg in contract_cfgs.items():
            # 라이브러리는 이미 위에서 처리했으므로 건너뛰기
            if contract_name in library_cfgs:
                continue
                
            contract_count += 1
            file_path = output_dir / f"{contract_name}_contract.json"
            try:
                serialized_data = self._serialize_contract_cfg(contract_cfg)
                serialized_data = self._json_safe(serialized_data)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(serialized_data, f, indent=2, ensure_ascii=False)
                saved_files[f"{contract_name}_contract"] = str(file_path)
                print(f"  ✓ {contract_name} contract")
            except Exception as e:
                print(f"  ✗ Failed to save contract {contract_name}: {e}")
        
        print(f"Serialization complete: {len(library_cfgs)} libraries, {contract_count} contracts")
        return saved_files

    def load_all_cfgs(self, input_dir: str = None) -> tuple[Dict[str, ContractCFG], Dict[str, LibraryCFG]]:
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
        
        # JSON 파일들 찾기
        json_files = list(input_dir.glob("*.json"))
        print(f"Found {len(json_files)} JSON files in {input_dir}")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 파일 타입에 따라 분류
                if json_file.name.endswith("_library.json"):
                    lib_name = json_file.stem.replace("_library", "")
                    library_cfg = self._deserialize_library_cfg(data)
                    library_cfgs[lib_name] = library_cfg
                    print(f"  ✓ Loaded library: {lib_name}")
                    
                elif json_file.name.endswith("_contract.json"):
                    contract_name = json_file.stem.replace("_contract", "")
                    contract_cfg = self._deserialize_contract_cfg(data)
                    contract_cfgs[contract_name] = contract_cfg
                    print(f"  ✓ Loaded contract: {contract_name}")
                    
                else:
                    # 일반적인 이름 패턴 시도
                    if data.get("type") == "LibraryCFG":
                        lib_name = data.get("library_name", json_file.stem)
                        library_cfg = self._deserialize_library_cfg(data)
                        library_cfgs[lib_name] = library_cfg
                        print(f"  ✓ Loaded library: {lib_name}")
                    elif data.get("type") == "ContractCFG":
                        contract_name = data.get("contract_name", json_file.stem)
                        contract_cfg = self._deserialize_contract_cfg(data)
                        contract_cfgs[contract_name] = contract_cfg
                        print(f"  ✓ Loaded contract: {contract_name}")
                    else:
                        print(f"  ? Unknown CFG type in {json_file.name}")
                        
            except Exception as e:
                print(f"  ✗ Failed to load {json_file.name}: {e}")
        
        print(f"Load complete: {len(contract_cfgs)} contracts, {len(library_cfgs)} libraries")
        return contract_cfgs, library_cfgs

    # Analyzer/CFGSerializer.py (CFGSerializer 클래스 내부)

    def _soltype_safe(self, t):
        try:
            from Domain.Type import SolType
        except Exception:
            SolType = None

        if t is None:
            return None
        if SolType is not None and isinstance(t, SolType):
            out = {"typeCategory": getattr(t, "typeCategory", None)}
            cat = out["typeCategory"]
            if cat == "elementary":
                out["elementaryTypeName"] = getattr(t, "elementaryTypeName", None)
                out["intTypeLength"] = getattr(t, "intTypeLength", None)
            elif cat == "array":
                out["arrayBaseType"] = self._soltype_safe(getattr(t, "arrayBaseType", None))
                out["arrayLength"] = getattr(t, "arrayLength", None)
                out["isDynamicArray"] = getattr(t, "isDynamicArray", False)
            elif cat == "mapping":
                out["mappingKeyType"] = self._soltype_safe(getattr(t, "mappingKeyType", None))
                out["mappingValueType"] = self._soltype_safe(getattr(t, "mappingValueType", None))
            elif cat == "struct":
                out["structTypeName"] = getattr(t, "structTypeName", None)
            elif cat == "enum":
                out["enumTypeName"] = getattr(t, "enumTypeName", None)
            elif cat == "userDefined":
                out["userTypeName"] = getattr(t, "userTypeName", None)
            return out
        # 모르는 타입이면 문자열
        return str(t)

    def _interval_safe(self, iv):
        try:
            from Domain.Interval import IntegerInterval, UnsignedIntegerInterval, BoolInterval
        except Exception:
            IntegerInterval = UnsignedIntegerInterval = BoolInterval = tuple()

        # Interval 계열
        if isinstance(iv, (IntegerInterval, UnsignedIntegerInterval, BoolInterval)):
            return {
                "_kind": iv.__class__.__name__,
                "min": getattr(iv, "min_value", None),
                "max": getattr(iv, "max_value", None),
                "bits": getattr(iv, "type_length", None),
            }
        # 원시 타입
        if iv is None or isinstance(iv, (bool, int, float, str)):
            return iv
        # 기타는 문자열로
        return str(iv)

    def _var_safe(self, v):
        try:
            from Domain.Variable import (
                Variables, ArrayVariable, StructVariable,
                MappingVariable, EnumVariable,
                StructDefinition, EnumDefinition
            )
        except Exception:
            # import 실패 시 그냥 문자열
            return None

        # Array
        if isinstance(v, ArrayVariable):
            return {
                "_kind": "ArrayVariable",
                "id": v.identifier,
                "scope": v.scope,
                "typeInfo": self._soltype_safe(getattr(v, "typeInfo", None)),
                "elements": [self._json_safe(e) for e in getattr(v, "elements", [])],
            }

        # Struct
        if isinstance(v, StructVariable):
            return {
                "_kind": "StructVariable",
                "id": v.identifier,
                "scope": v.scope,
                "typeInfo": self._soltype_safe(getattr(v, "typeInfo", None)),
                "members": {k: self._json_safe(val) for k, val in getattr(v, "members", {}).items()},
            }

        # Mapping
        if isinstance(v, MappingVariable):
            return {
                "_kind": "MappingVariable",
                "id": v.identifier,
                "scope": v.scope,
                "typeInfo": self._soltype_safe(getattr(v, "typeInfo", None)),
                "mapping": {str(k): self._json_safe(val) for k, val in getattr(v, "mapping", {}).items()},
            }

        # EnumVariable
        if isinstance(v, EnumVariable):
            return {
                "_kind": "EnumVariable",
                "id": v.identifier,
                "scope": v.scope,
                "enum": getattr(getattr(v, "typeInfo", None), "enumTypeName", None),
                "members": getattr(v, "members", {}),
                "value": self._json_safe(getattr(v, "value", None)),
                "valueIndex": getattr(v, "valueIndex", None),
            }

        # 일반 Variables (leaf)
        if isinstance(v, Variables):
            return {
                "_kind": "Variables",
                "id": v.identifier,
                "scope": v.scope,
                "isConstant": getattr(v, "isConstant", False),
                "typeInfo": self._soltype_safe(getattr(v, "typeInfo", None)),
                "value": self._interval_safe(getattr(v, "value", None)),
            }

        # Struct/Enum Definition (Library/ContractCFG.serialize_for_storage 안의 structDefs/enumDefs 보호)
        if "StructDefinition" in v.__class__.__name__:
            return {
                "_kind": "StructDefinition",
                "struct_name": getattr(v, "struct_name", None),
                "members": [
                    {
                        "member_name": m.get("member_name"),
                        "member_type": self._soltype_safe(m.get("member_type")),
                    }
                    for m in getattr(v, "members", [])
                ],
            }
        if "EnumDefinition" in v.__class__.__name__:
            return {
                "_kind": "EnumDefinition",
                "enum_name": getattr(v, "enum_name", None),
                "members": list(getattr(v, "members", [])),
            }

        return None

    def _json_safe(self, obj):
        # 원시
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        # 컨테이너
        if isinstance(obj, (list, tuple, set)):
            return [self._json_safe(x) for x in obj]
        if isinstance(obj, dict):
            return {str(k): self._json_safe(v) for k, v in obj.items()}

        # Variables / 파생
        v = self._var_safe(obj)
        if v is not None:
            return v

        # Interval
        iv = self._interval_safe(obj)
        # _interval_safe는 비-interval이면 문자열을 돌려줄 수 있으니, 그대로 반환
        return iv
