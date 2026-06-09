package com.example.usermanagement.service;

import com.example.usermanagement.repository.UserRepository;
import com.example.usermanagement.model.User;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class UserService {

    private final UserRepository userRepository;

    public UserService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public User crearUsuario(User usuario) {
        return userRepository.save(usuario);
    }

    public List<User> obtenerTodos() {
        return userRepository.findAll();
    }

    public User obtenerPorId(Long id) {
        return userRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Usuario no encontrado"));
    }

    public User actualizarUsuario(Long id, User usuario) {
        User usuarioExistente = obtenerPorId(id);
        usuarioExistente.setNombre(usuario.getNombre());
        usuarioExistente.setEmail(usuario.getEmail());
        usuarioExistente.setRol(usuario.getRol());
        return userRepository.save(usuarioExistente);
    }

    public void eliminarUsuario(Long id) {
        userRepository.deleteById(id);
    }
}