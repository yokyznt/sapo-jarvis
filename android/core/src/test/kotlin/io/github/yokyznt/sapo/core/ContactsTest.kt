package io.github.yokyznt.sapo.core

import kotlin.test.assertEquals
import kotlin.test.assertNull
import org.junit.Test

class ContactsTest {
    private val agenda = listOf("Mamá ❤️", "Papá", "Juan Pérez", "Juan López", "Fernanda Ruiz", "Luis", "Ana", "Anahí", "José Luis")

    @Test
    fun ownershipAndAccents() {
        assertEquals("Mamá ❤️", Contacts.best("mi mamá", agenda))
        assertEquals("Mamá ❤️", Contacts.best("MAMA", agenda))
        assertEquals("Papá", Contacts.best("a mi papá", agenda))
        assertEquals("Mamá", Contacts.best("mi mamá", listOf("Juan", "Mamá", "Papá")))
    }

    @Test
    fun shortPrefix() {
        assertEquals("Mamá ❤️", Contacts.best("ma", listOf("Mamá ❤️", "Juan", "Pedro")))
        assertEquals("Fernanda Ruiz", Contacts.best("fer", agenda))
    }

    @Test
    fun oneLetterTypoOnLongNames() {
        assertEquals("Fernanda Ruiz", Contacts.best("Fernada", agenda))
        assertEquals("Fernanda Ruiz", Contacts.best("fernamda", agenda))
        assertEquals("Rodrigo", Contacts.best("rodrgo", listOf("Rodrigo", "Ana")))
        assertNull(Contacts.best("Lus", listOf("Luis", "Ana")))
        assertNull(Contacts.best("fernandoo", listOf("Fernanda")))
    }

    @Test
    fun exactBeatsLonger() {
        assertEquals("Ana", Contacts.best("ana", agenda))
        assertEquals("Luis", Contacts.best("luis", agenda))
        assertEquals("Mamá ❤️", Contacts.best("mamá", listOf("Mamá ❤️", "Mamá Lucha")))
    }

    @Test
    fun fullNameWins() {
        assertEquals("Juan Pérez", Contacts.best("juan perez", agenda))
        assertEquals("Juan López", Contacts.best("Juan López", agenda))
        assertEquals("José Luis", Contacts.best("jose", agenda))
    }

    @Test
    fun tieIsNull() {
        assertNull(Contacts.best("juan", agenda))
        assertNull(Contacts.best("ma", listOf("Mamá", "Mario")))
    }

    @Test
    fun nothingIsNull() {
        assertNull(Contacts.best("Roberto", agenda))
        assertNull(Contacts.best("", agenda))
        assertNull(Contacts.best("mi", agenda))
        assertNull(Contacts.best("ana", emptyList()))
        assertNull(Contacts.best("❤️", agenda))
    }

    @Test
    fun duplicatesAreOne() {
        assertEquals("Ana", Contacts.best("ana", listOf("Ana", "Ana", "Pedro")))
    }
}
