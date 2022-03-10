import textwrap
from dataclasses import dataclass, is_dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

from addicty import Dict as _Addict

NODEFAULT = "< NO DEFAULT >"


def nonnegative_validator(name, value):
    if value is not None and value < 0:
        raise ValueError(f"values for {name!r} have to be non-negative")


def pretty(i):
    try:
        t = i.__name__
    except AttributeError:
        t = repr(i)
    if t is None:
        t = repr(i)
    return t


class subtype_validator:
    """
    Validates that all items in an iterable are a type.
    """

    def __init__(self, subtype):
        self.subtype = subtype

    def __call__(self, name, value):
        for i in value:
            if not isinstance(i, self.subtype):
                raise TypeError(f"items for {name!r} have to be {pretty(self.subtype)}")


class subvalue_type_validator:
    """
    Validates that all values in a mapping are a type.
    """

    def __init__(self, subtype):
        self.subtype = subtype

    def __call__(self, name, value):
        for k, v in value.items():
            if not isinstance(v, self.subtype):
                raise TypeError(
                    f"values for {name!r} have to be {pretty(self.subtype)}"
                )


class Setting:
    """A generic setting value."""

    def validate(self, value):
        return value


class TypeRequired(Setting):
    def __init__(self, type, default=None, validators=(), doc=None, allow_none=True):
        self.type = type
        self.default = default
        self.allow_none = allow_none
        self.validators = validators
        if doc:
            self.__doc__ = textwrap.dedent(doc)

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if not instance:
            return self
        try:
            return instance.__dict__[self.name]
        except KeyError:
            if self.default is NODEFAULT:
                raise ValueError(f"there is no default value for {self.name!r}")
            return self.default

    def __set__(self, instance, value):
        if value is not self:
            self.validate(value)
            instance.__dict__[self.name] = value
        else:
            if self.default is NODEFAULT:
                raise ValueError(f"{self.name!r} is required")
            instance.__dict__[self.name] = self.default

    def __delete__(self, instance):
        del instance.__dict__[self.name]

    def validate(self, value):
        if not isinstance(value, self.type):
            if not (self.allow_none and value is None):
                raise TypeError(
                    f"{self.name!r} values must be of type {pretty(self.type)}"
                )
        for validator in self.validators:
            validator(self.name, value)
        return value


class Enumerated(Setting):
    def __repr__(self):
        return f"Enumerated({self.allowed_values})"

    @classmethod
    def Lowercase(cls, allowed_values):
        return cls(allowed_values, require_lowercase=True)

    def __init__(self, allowed_values, require_lowercase=False, doc=None):
        self.default = allowed_values[0]
        self.allowed_values = set(allowed_values)
        self.lowercase = require_lowercase
        if doc:
            self.__doc__ = textwrap.dedent(doc)
        if require_lowercase:
            self.allowed_values = {str(i).lower() for i in self.allowed_values}

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if not instance:
            return self
        try:
            return instance.__dict__[self.name]
        except KeyError:
            return self.default

    def __delete__(self, instance):
        del instance.__dict__[self.name]

    def __set__(self, instance, value):
        if value is not self:
            if self.lowercase:
                value = str(value).lower()
            self.validate(value)
            instance.__dict__[self.name] = value

    def validate(self, value):
        if value not in self.allowed_values:
            raise ValueError(
                f"{self.name!r} values must be one of {self.allowed_values!r}, not {value!r}"
            )
        return value


class RequireBool(TypeRequired):
    """This setting must be a boolean (true or false)."""

    def __init__(self, default=None, validators=(), doc=None):
        super().__init__(type=bool, default=default, validators=validators, doc=doc)

    def __repr__(self):
        return "RequireBool"


class RequireInteger(TypeRequired):
    """This setting must be an integer."""

    def __init__(self, default=None, validators=(), doc=None):
        super().__init__(type=int, default=default, validators=validators, doc=doc)

    def __repr__(self):
        return "RequireInteger"

    @classmethod
    def NonNegative(cls, **kwargs):
        return cls(validators=(nonnegative_validator,), **kwargs)


class RequireString(TypeRequired):
    """This setting must be a string."""

    def __init__(self, **kwargs):
        super().__init__(type=str, **kwargs)

    def __repr__(self):
        return "RequireString"


class RequireSequence(TypeRequired):
    """This setting must be a sequence (e.g. list or tuple)."""

    def __init__(self, **kwargs):
        super().__init__(type=Sequence, **kwargs)

    def __repr__(self):
        return "RequireSequence"


class RequireList(TypeRequired):
    """This setting must be a list."""

    def __init__(self, **kwargs):
        super().__init__(type=list, **kwargs)

    def __repr__(self):
        return "RequireList"


class RequireListOf(RequireList):
    """This setting must be a sequence (e.g. list or tuple)."""

    def __init__(self, itemtype, default=None, validators=(), doc=None):
        self.itemtype = itemtype
        validator = subtype_validator(self.itemtype)
        validators = tuple(validators) + (validator,)
        super().__init__(default=default, validators=validators, doc=doc)

    def __repr__(self):
        return f"RequireListOf({pretty(self.itemtype)})"

    def __set__(self, instance, value):
        if value is not self:
            value = self.validate(value)
            instance.__dict__[self.name] = value
        else:
            instance.__dict__[self.name] = self.default

    def validate(self, value):
        if not isinstance(value, self.type):
            if not (self.allow_none and value is None):
                raise TypeError(f"{self.name!r} values must be of type {self.type}")
        for validator in self.validators:
            try:
                validator(self.name, value)
            except TypeError:
                if is_dataclass(self.itemtype):
                    new_value = []
                    for i in value:
                        if isinstance(i, Mapping):
                            try:
                                i = self.itemtype(**i)
                            except TypeError as err:
                                if "__init__" in err.args[0]:
                                    err.args = (
                                        err.args[0].replace(
                                            "__init__", self.itemtype.__name__
                                        ),
                                    ) + err.args[1:]
                                raise err
                        new_value.append(i)
                    value = new_value
                    validator(self.name, value)
                else:
                    raise
        return value


class RequireSet(TypeRequired):
    """This setting must be a mapping."""

    def __init__(self, **kwargs):
        super().__init__(type=set, **kwargs)

    def __repr__(self):
        return "RequireSet"

    def validate(self, value):
        if not isinstance(value, self.type):
            if not (self.allow_none and value is None):
                if isinstance(value, Sequence):
                    new_value = set(value)
                    if len(value) != len(new_value):
                        raise ValueError(
                            f"all elements in {self.name!r} must be unique"
                        )
                    value = new_value
                else:
                    raise TypeError(
                        f"{self.name!r} values must be of type {pretty(self.type)}"
                    )
        for validator in self.validators:
            validator(self.name, value)
        return value


class RequireSetOf(RequireSet):
    """This setting must be a set (e.g. a collection of unique items)."""

    def __init__(self, itemtype, default=None, validators=(), doc=None):
        self.itemtype = itemtype
        validator = subtype_validator(self.itemtype)
        validators = tuple(validators) + (validator,)
        super().__init__(default=default, validators=validators, doc=doc)

    def __repr__(self):
        return f"RequireSetOf({pretty(self.itemtype)})"

    def __set__(self, instance, value):
        if value is not self:
            value = self.validate(value)
            instance.__dict__[self.name] = value
        else:
            instance.__dict__[self.name] = self.default

    def validate(self, value):
        if not isinstance(value, self.type):
            if not (self.allow_none and value is None):
                if isinstance(value, Sequence):
                    new_value = set(value)
                    if len(value) != len(new_value):
                        raise ValueError(
                            f"all elements in {self.name!r} must be unique"
                        )
                    value = new_value
                else:
                    raise TypeError(
                        f"{self.name!r} values must be of type {pretty(self.type)}"
                    )
        for validator in self.validators:
            try:
                validator(self.name, value)
            except TypeError:
                if is_dataclass(self.itemtype):
                    new_value = []
                    for i in value:
                        if isinstance(i, Mapping):
                            try:
                                i = self.itemtype(**i)
                            except TypeError as err:
                                if "__init__" in err.args[0]:
                                    err.args = (
                                        err.args[0].replace(
                                            "__init__", self.itemtype.__name__
                                        ),
                                    ) + err.args[1:]
                                raise err
                        new_value.append(i)
                    value = new_value
                    validator(self.name, value)
                else:
                    raise
        return value


class RequireDict(TypeRequired):
    """This setting must be a mapping."""

    def __init__(self, **kwargs):
        super().__init__(type=dict, **kwargs)

    def __repr__(self):
        return "RequireDict"


class RequireDictOfStrTo(RequireDict):
    """This setting must be a sequence (e.g. list or tuple)."""

    def __init__(self, itemtype, default=None, validators=(), doc=None):
        self.itemtype = itemtype
        validator1 = subtype_validator(str)
        validator2 = subvalue_type_validator(self.itemtype)
        validators = tuple(validators) + (validator1, validator2)
        super().__init__(default=default, validators=validators, doc=doc)

    def __repr__(self):
        return f"RequireDictOfStrTo({pretty(self.itemtype)})"

    def __set__(self, instance, value):
        if value is not self:
            value = self.validate(value)
            instance.__dict__[self.name] = value
        else:
            instance.__dict__[self.name] = self.default

    def validate(self, value):
        if not isinstance(value, self.type):
            if not (self.allow_none and value is None):
                raise TypeError(f"{self.name!r} values must be of type {self.type}")
        for validator in self.validators:
            try:
                validator(self.name, value)
            except TypeError:
                if is_dataclass(self.itemtype):
                    new_value = {}
                    for i, v in value.items():
                        if isinstance(v, Mapping):
                            try:
                                v = self.itemtype(**v)
                            except TypeError as err:
                                if "__init__" in err.args[0]:
                                    err.args = (
                                        err.args[0].replace(
                                            "__init__", self.itemtype.__name__
                                        ),
                                    ) + err.args[1:]
                                raise err
                        new_value[i] = v
                    value = new_value
                    validator(self.name, value)
                else:
                    raise
        return value


class RequireA(TypeRequired):
    def __init__(self, type, default=None, validators=(), doc=None):
        super().__init__(type=type, default=default, validators=validators, doc=doc)

    def __repr__(self):
        return f"RequireA({pretty(self.type)})"

    def __set__(self, instance, value):
        if value is not self:
            value = self.validate(value)
            instance.__dict__[self.name] = value
        else:
            instance.__dict__[self.name] = self.default

    def validate(self, value):
        if not isinstance(value, self.type):
            if not (self.allow_none and value is None):
                if is_dataclass(self.type) and isinstance(value, Mapping):
                    # Try making the child type
                    value = self.type(**value)
                else:
                    raise TypeError(f"{self.name!r} values must be of type {self.type}")
        for validator in self.validators:
            validator(self.name, value)


class CascadingSettings:
    def _append_or_overwrite(self, source):
        for k, v in source.items():
            attr = getattr(self.__class__, k, None)
            if not isinstance(attr, Setting):
                raise ValueError(f"{k!r} is not a valid setting")
            if isinstance(attr, RequireSequence):
                v = attr.validate(v)
                self.__dict__[k] = self.__dict__[k] + v
            elif isinstance(attr, RequireSet):
                v = attr.validate(v)
                self.__dict__[k] |= v
            elif isinstance(attr, RequireDict):
                v = attr.validate(v)
                self.__dict__[k].update(v)
            elif isinstance(attr, RequireA):
                v = attr.validate(v)
                if is_dataclass(attr.type):
                    existing = getattr(self, k, None)
                    if existing is None:
                        replacement = v
                    else:
                        replacement = replace(existing, **v.__dict__)
                    self.__dict__[k] = replacement
                else:
                    self.__dict__[k] = v
            else:
                v = attr.validate(v)
                self.__dict__[k] = v

    def _backfill(self, source):
        for k, v in source.items():
            attr = getattr(self.__class__, k, None)
            if not isinstance(attr, Setting):
                raise ValueError(f"{k!r} is not a valid setting")
            if k not in self.__dict__ or self.__dict__[k] is None:
                v = attr.validate(v)
                self.__dict__[k] = v

    def overload(self, filename):
        if isinstance(filename, Path):
            filename = str(filename)
        source = _Addict.load(filename).to_dict()
        self._append_or_overwrite(source)

    def underload(self, filename):
        if isinstance(filename, Path):
            filename = str(filename)
        source = _Addict.load(filename).to_dict()
        self._backfill(source)

    @classmethod
    def initialize(cls, filename):
        if isinstance(filename, Path):
            filename = str(filename)
        source = _Addict.load(filename).to_dict()
        return cls(**source)


class configclass:
    def __new__(cls, baseclass=None, allow_arbitrary=True):
        self = super().__new__(cls)
        self.allow_arbitrary = allow_arbitrary
        if baseclass is None:
            return self
        else:
            return self.__call__(baseclass)

    def __call__(self, baseclass):
        @dataclass
        class CascadingSettingsDef(dataclass(baseclass), CascadingSettings):
            _allow_arbitrary = self.allow_arbitrary

            def __init__(self, *args, **kwargs):
                expects = self.__class__.__bases__[0].__dict__.keys()
                expected_kwargs = {}
                unexpected_kwargs = {}
                for k, v in kwargs.items():
                    if k in expects:
                        expected_kwargs[k] = v
                    else:
                        unexpected_kwargs[k] = v
                if not self._allow_arbitrary and unexpected_kwargs:
                    raise ValueError(f"unexpected settings: {unexpected_kwargs!r}")
                super().__init__(*args, **expected_kwargs)
                self.__dict__.update(unexpected_kwargs)

        CascadingSettingsDef.__name__ = baseclass.__name__
        CascadingSettingsDef.__qualname__ = baseclass.__qualname__
        CascadingSettingsDef.__doc__ = baseclass.__doc__
        CascadingSettingsDef.__module__ = baseclass.__module__
        return CascadingSettingsDef
