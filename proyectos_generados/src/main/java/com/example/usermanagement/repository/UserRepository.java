package com.example.usermanagement.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface UserRepository extends JpaRepository<User, Long> {
    List<User> findByRole(String role);
    boolean existsByEmail(String email);
    User findByEmail(String email);
}